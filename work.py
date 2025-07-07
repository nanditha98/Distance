from flask import Flask, render_template, request, send_from_directory
import os
import csv
import openrouteservice
import time
import requests

app = Flask(__name__)

app.config['OUTPUT_FOLDER'] = os.path.join(os.getcwd(), 'outputs')
os.makedirs("uploads", exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

API_KEY = "5b3ce3597851110001cf6248242930a613eb44fba576aa3429a6f74b"  # Replace with your own valid OpenRouteService API key
BATCH_SIZE = 40
quota_exceeded = False

def read_coordinates_from_csv(file_path, invalid_rows_file):
    coordinates = []
    invalid_rows = []
    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                lat = float(row['Latitude'].strip())
                lon = float(row['Longitude'].strip())
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    raise ValueError("Invalid lat/lon range")
                coordinates.append({
                    'lat': lat,
                    'lon': lon,
                    'refno': row['RefNo'],
                    'address': row['Address'],
                    'coordinates': (lon, lat)
                })
            except ValueError as e:
                print(f"Invalid row detected: {row} - Error: {e}")
                invalid_rows.append(row)
    if invalid_rows:
        with open(invalid_rows_file, 'w', newline='') as invalid_file:
            writer = csv.DictWriter(invalid_file, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(invalid_rows)
    print(f"Total valid coordinates: {len(coordinates)}")
    return coordinates

# Snap a point to the nearest routable road

# def snap_to_road(API_KEY, lon, lat, radius=1000, max_retries=3):
#     url = f"https://api.openrouteservice.org /v2/snap/driving-car?radius={radius}"
#     headers = {
#         'Authorization': API_KEY,
#         'Content-Type': 'application/json'
#     }
#     body = {"locations": [[lon, lat]]}

#     for attempt in range(max_retries):
#         try:
#             response = requests.post(url, headers=headers, json=body)
#             print(f"Snap response for ({lon}, {lat}): {response.status_code}")
#             response.raise_for_status()
#             snapped_data = response.json()

#             if snapped_data and 'snapped_points' in snapped_data:
#                 snapped_location = snapped_data['snapped_points'][0]['location']
#                 print(f"Snapped ({lon}, {lat}) to {snapped_location}")
#                 return {"location": snapped_location}
#             else:
#                 print(f"No snapped point found for ({lon}, {lat})")
#                 return None

#         except requests.exceptions.HTTPError as e:
#             print(f"Attempt {attempt+1} failed for ({lon}, {lat}): {e}")
#             if response.status_code in [502, 503, 504]:  # Retry for server errors
#                 time.sleep(2)
#                 continue
#             else:
#                 break  # Don't retry for other errors
#         except requests.exceptions.RequestException as e:
#             print(f"Request failed: {e}")
#             break
#     print(f"Failed to snap ({lon}, {lat}) after {max_retries} attempts")
#     return None




def snap_to_road(api_key, lon, lat):
    url = "https://api.openrouteservice.org/v2/snap/driving-car"
    
    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }
    
    body = {
        "locations": [[lon, lat]]
    }
    
    try:
        response = requests.post(url, headers=headers, json=body)
        print(f"Snap response for ({lon}, {lat}): {response.status_code}")
        response.raise_for_status()
        
        snapped_data = response.json()
        print(f"Full Snap API Response: {snapped_data}")  # Helpful for debugging

        # ORS sometimes uses 'snappedPoints' key depending on version
        if 'snapped_points' in snapped_data and snapped_data['snapped_points']:
            snapped_location = snapped_data['snapped_points'][0]['location']
            print(f"Snapped ({lon}, {lat}) to {snapped_location}")
            return {"location": snapped_location}
        
        elif 'snappedPoints' in snapped_data and snapped_data['snappedPoints']:
            snapped_location = snapped_data['snappedPoints'][0]['location']
            print(f"Snapped ({lon}, {lat}) to {snapped_location}")
            return {"location": snapped_location}
        
        else:
            print(f"No snapped point found for ({lon}, {lat})")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Failed to snap ({lon}, {lat}): {e}")
        return None


# Calculate road distance between two snapped points
def calculate_road_distance(coord1, coord2):
    global quota_exceeded
    client = openrouteservice.Client(key=API_KEY)
    coords = [coord1, coord2]
    try:
        result = client.directions(coords)
        distance_m = result['routes'][0]['summary']['distance']
        return distance_m / 1000  # Convert meters to kilometers
    except openrouteservice.exceptions.ApiError as e:
        if "Quota exceeded" in str(e):
            print("Quota exceeded! Stopping calculations.")
            quota_exceeded = True
        print(f"API Error: {e}")
    except Exception as e:
        print(f"Unexpected error calculating distance: {e}")
    return None

# Write results to CSV
def write_results_to_csv(output_file, results):
    file_exists = os.path.exists(output_file)
    with open(output_file, 'a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow([
                'Source RefNo', 'Source Latitude', 'Source Longitude', 'Source Address',
                'Destination RefNo', 'Destination Latitude', 'Destination Longitude', 'Destination Address',
                'Distance (km)'
            ])
        for result in results:
            writer.writerow(result)

# Batch processing with snapping and unreachable handling
def process_batches(source_coords, destination_coords, output_file):
    global quota_exceeded
    results = []
    for i in range(0, len(source_coords), BATCH_SIZE):
        for j in range(0, len(destination_coords), BATCH_SIZE):
            batch_results = []
            for src in source_coords[i:i+BATCH_SIZE]:
                snapped_src = snap_to_road(API_KEY, src['lon'], src['lat'])
                if not snapped_src:
                    continue
                for dest in destination_coords[j:j+BATCH_SIZE]:
                    snapped_dest = snap_to_road(API_KEY, dest['lon'], dest['lat'])
                    if not snapped_dest:
                        continue
                    if quota_exceeded:
                        return results
                    distance = calculate_road_distance(snapped_src['location'], snapped_dest['location'])
                    if distance is not None:
                        batch_results.append([
                            src['refno'], src['lat'], src['lon'], src['address'],
                            dest['refno'], dest['lat'], dest['lon'], dest['address'],
                            round(distance, 2)
                        ])
                    else:
                        batch_results.append([
                            src['refno'], src['lat'], src['lon'], src['address'],
                            dest['refno'], dest['lat'], dest['lon'], dest['address'],
                            "Unreachable"
                        ])
            results.extend(batch_results)
            write_results_to_csv(output_file, batch_results)
            time.sleep(1)
    return results

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/calculate", methods=["POST"])
def calculate():
    global quota_exceeded
    quota_exceeded = False
    if "source_csv" not in request.files or "destination_csv" not in request.files:
        return "Source or destination file missing", 400

    source_file = request.files["source_csv"]
    destination_file = request.files["destination_csv"]
    if source_file.filename == "" or destination_file.filename == "":
        return "One or both files are empty", 400

    source_path = os.path.join("uploads", source_file.filename)
    destination_path = os.path.join("uploads", destination_file.filename)
    source_file.save(source_path)
    destination_file.save(destination_path)

    invalid_source_file = os.path.join(app.config['OUTPUT_FOLDER'], "invalid_source_rows.csv")
    invalid_destination_file = os.path.join(app.config['OUTPUT_FOLDER'], "invalid_destination_rows.csv")

    source_coords = read_coordinates_from_csv(source_path, invalid_source_file)
    destination_coords = read_coordinates_from_csv(destination_path, invalid_destination_file)

    output_file_name = "road_distances_output.csv"
    output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], output_file_name)

    process_batches(source_coords, destination_coords, output_file_path)

    return render_template(
        "result.html",
        output_file=output_file_name,
        quota_exceeded=quota_exceeded,
        invalid_source_file="invalid_source_rows.csv",
        invalid_destination_file="invalid_destination_rows.csv",
        status="Complete" if not quota_exceeded else "Partially Complete"
    )

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)
    return f"File '{filename}' not found.", 404

if __name__ == "__main__":
    app.run(debug=True, port=5000)
