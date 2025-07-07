# # from flask import Flask, render_template, request, send_from_directory
# # import os
# # import csv
# # import openrouteservice
# # import time
# # import requests

# # # Initialize Flask app
# # app = Flask(__name__)

# # # Set the output folder path for downloaded files
# # app.config['OUTPUT_FOLDER'] = os.path.join(os.getcwd(), 'outputs')
# # os.makedirs("uploads", exist_ok=True)
# # os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# # # OpenRouteService API key
# # API_KEY = "5b3ce3597851110001cf6248a75e6026694c41f4a0790e63fc25a444"

# # # Batch size
# # BATCH_SIZE = 40
# # quota_exceeded = False

# # # Reverse geocoding function
# # def reverse_geocode(coord):
# #     try:
# #         url = "https://api.openrouteservice.org/geocode/reverse"
# #         params = {
# #             'api_key': API_KEY,
# #             'point.lon': coord[0],
# #             'point.lat': coord[1]
# #         }
# #         response = requests.get(url, params=params)
# #         if response.status_code == 200:
# #             data = response.json()
# #             if data['features']:
# #                 return data['features'][0]['properties']['label']
# #         else:
# #             print(f"Reverse geocoding failed for {coord}: {response.text}")
# #     except Exception as e:
# #         print(f"Reverse geocoding error for {coord}: {e}")
# #     return None

# # # Snap to nearest routable point
# # def snap_to_nearest(coord):
# #     try:
# #         url = "https://api.openrouteservice.org/v2/nearest/driving-car"
# #         params = {
# #             'api_key': API_KEY,
# #             'point': f"{coord[0]},{coord[1]}"
# #         }
# #         response = requests.get(url, params=params)
# #         if response.status_code == 200:
# #             data = response.json()
# #             snapped_coord = data['features'][0]['geometry']['coordinates']
# #             return tuple(snapped_coord)
# #         else:
# #             print(f"Snap to nearest failed for {coord}: {response.text}")
# #     except Exception as e:
# #         print(f"Snap to nearest error for {coord}: {e}")
# #     return None

# # # Read coordinates from CSV
# # def read_coordinates_from_csv(file_path, invalid_rows_file):
# #     coordinates = []
# #     invalid_rows = []

# #     with open(file_path, 'r') as file:
# #         reader = csv.DictReader(file)
# #         for row in reader:
# #             try:
# #                 lat = float(row['Latitude'].strip())
# #                 lon = float(row['Longitude'].strip())
# #                 if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
# #                     raise ValueError("Coordinates out of range")

# #                 address = row.get('Address', '').strip()
# #                 if not address:
# #                     address = reverse_geocode((lon, lat))

# #                 coordinates.append({
# #                     'lat': lat,
# #                     'lon': lon,
# #                     'refno': row['RefNo'],
# #                     'address': address,
# #                     'coordinates': (lon, lat)
# #                 })
# #             except Exception as e:
# #                 print(f"Invalid row: {row} - {e}")
# #                 invalid_rows.append(row)

# #     if invalid_rows:
# #         with open(invalid_rows_file, 'w', newline='') as invalid_file:
# #             writer = csv.DictWriter(invalid_file, fieldnames=reader.fieldnames)
# #             writer.writeheader()
# #             writer.writerows(invalid_rows)
# #         print(f"Invalid rows saved to {invalid_rows_file}")

# #     return coordinates

# # # Calculate road distance
# # def calculate_road_distance(coord1, coord2):
# #     global quota_exceeded
# #     client = openrouteservice.Client(key=API_KEY)

# #     snapped_coord1 = snap_to_nearest(coord1)
# #     snapped_coord2 = snap_to_nearest(coord2)

# #     if not snapped_coord1 or not snapped_coord2:
# #         print("Could not snap one or both coordinates to a routable point.")
# #         return None

# #     try:
# #         result = client.directions([snapped_coord1, snapped_coord2])
# #         distance_m = result['routes'][0]['summary']['distance']
# #         return distance_m / 1000  # in km
# #     except openrouteservice.exceptions.ApiError as e:
# #         if "Quota exceeded" in str(e):
# #             print("Quota exceeded. Stopping calculations.")
# #             quota_exceeded = True
# #         else:
# #             print(f"API Error: {e}")
# #     except Exception as e:
# #         print(f"Distance calculation error: {e}")
# #     return None

# # # Write results to CSV
# # def write_results_to_csv(output_file, results):
# #     file_exists = os.path.exists(output_file)
# #     with open(output_file, 'a', newline='') as file:
# #         writer = csv.writer(file)
# #         if not file_exists:
# #             writer.writerow(['Source RefNo', 'Source Latitude', 'Source Longitude', 'Source Address',
# #                              'Destination RefNo', 'Destination Latitude', 'Destination Longitude', 'Destination Address',
# #                              'Distance (km)'])
# #         for result in results:
# #             writer.writerow(result)

# # # Process distances
# # def process_batches(source_coords, destination_coords, output_file):
# #     global quota_exceeded
# #     results = []

# #     for i in range(0, len(source_coords), BATCH_SIZE):
# #         for j in range(0, len(destination_coords), BATCH_SIZE):
# #             batch_results = []
# #             for coord1 in source_coords[i:i+BATCH_SIZE]:
# #                 for coord2 in destination_coords[j:j+BATCH_SIZE]:
# #                     if quota_exceeded:
# #                         return results
# #                     distance = calculate_road_distance(coord1['coordinates'], coord2['coordinates'])
# #                     time.sleep(0.5)
# #                     batch_results.append([
# #                         coord1['refno'], coord1['lat'], coord1['lon'], coord1['address'],
# #                         coord2['refno'], coord2['lat'], coord2['lon'], coord2['address'],
# #                         round(distance, 2) if distance is not None else "NA"
# #                     ])
# #             results.extend(batch_results)
# #             write_results_to_csv(output_file, batch_results)
# #             time.sleep(1)
# #     return results

# # # Routes
# # @app.route("/")
# # def index():
# #     return render_template("index.html")

# # @app.route("/calculate", methods=["POST"])
# # def calculate():
# #     global quota_exceeded
# #     quota_exceeded = False

# #     if "source_csv" not in request.files or "destination_csv" not in request.files:
# #         return "Source or destination file missing", 400

# #     source_file = request.files["source_csv"]
# #     destination_file = request.files["destination_csv"]

# #     if source_file.filename == "" or destination_file.filename == "":
# #         return "One or both files are empty", 400

# #     source_path = os.path.join("uploads", source_file.filename)
# #     destination_path = os.path.join("uploads", destination_file.filename)
# #     source_file.save(source_path)
# #     destination_file.save(destination_path)

# #     invalid_source_file = os.path.join(app.config['OUTPUT_FOLDER'], "invalid_source_rows.csv")
# #     invalid_destination_file = os.path.join(app.config['OUTPUT_FOLDER'], "invalid_destination_rows.csv")

# #     source_coords = read_coordinates_from_csv(source_path, invalid_source_file)
# #     destination_coords = read_coordinates_from_csv(destination_path, invalid_destination_file)

# #     output_file = os.path.join(app.config['OUTPUT_FOLDER'], "road_distances_output.csv")
# #     process_batches(source_coords, destination_coords, output_file)

# #     return render_template("result.html", output_file="road_distances_output.csv",
# #                            quota_exceeded=quota_exceeded,
# #                            invalid_source_file="invalid_source_rows.csv",
# #                            invalid_destination_file="invalid_destination_rows.csv",
# #                            status="Complete" if not quota_exceeded else "Partially Complete")

# # @app.route('/download/<filename>')
# # def download_file(filename):
# #     try:
# #         file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
# #         if os.path.exists(file_path):
# #             return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)
# #         return f"File '{filename}' not found.", 404
# #     except Exception as e:
# #         return f"Error: {str(e)}", 500

# # # Test reverse geocode
# # @app.route("/reverse")
# # def reverse_test():
# #     lon = request.args.get("lon", type=float)
# #     lat = request.args.get("lat", type=float)
# #     if lon is None or lat is None:
# #         return "Provide lon and lat as query params", 400
# #     address = reverse_geocode((lon, lat))
# #     return address if address else "Address not found"

# # if __name__ == "__main__":
# #     app.run(debug=True, port=5000)


# from flask import Flask, render_template, request, send_from_directory
# import os
# import csv
# import openrouteservice
# import time
# import requests

# app = Flask(__name__)
# app.config['OUTPUT_FOLDER'] = os.path.join(os.getcwd(), 'outputs')
# os.makedirs("uploads", exist_ok=True)
# os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# API_KEY = "5b3ce3597851110001cf6248a75e6026694c41f4a0790e63fc25a444"  # Replace with your valid key
# BATCH_SIZE = 40
# quota_exceeded = False

# client = openrouteservice.Client(key=API_KEY)

# # Snap coordinate to nearest routable point


# def snap_to_nearest(coord):
#     try:
#         lon = float(coord[0])
#         lat = float(coord[1])
        
#         url = "https://api.openrouteservice.org/v2/snap/driving-car"
#         headers = {
#             'Authorization': API_KEY,
#             'Content-Type': 'application/json'
#         }
        
#         payload = {
#             "locations": [[lon, lat]]
#         }
        
#         response = requests.post(url, json=payload, headers=headers)
#         response.raise_for_status()
        
#         data = response.json()
#         snapped_coords = data['locations'][0]
        
#         print(f"Snapped {coord} to {snapped_coords}")
#         return tuple(snapped_coords)
    
#     except requests.exceptions.HTTPError as errh:
#         print(f"Failed to snap {coord}: {errh} - {response.text}")
#         return None
#     except Exception as e:
#         print(f"Failed to snap {coord}: {e}")
#         return None






# # Read coordinates from CSV
# def read_coordinates_from_csv(file_path, invalid_rows_file):
#     coordinates = []
#     invalid_rows = []
#     with open(file_path, 'r') as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             try:
#                 lat = float(row['Latitude'].strip())
#                 lon = float(row['Longitude'].strip())
#                 if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
#                     raise ValueError(f"Invalid lat/lon range: {lat}, {lon}")

#                 coordinates.append({
#                     'lat': lat,
#                     'lon': lon,
#                     'refno': row['RefNo'],
#                     'address': row['Address'],
#                     'coordinates': (lon, lat)
#                 })
#             except ValueError as e:
#                 print(f"Invalid row detected: {row} - {e}")
#                 invalid_rows.append(row)

#     if invalid_rows:
#         with open(invalid_rows_file, 'w', newline='') as invalid_file:
#             writer = csv.DictWriter(invalid_file, fieldnames=reader.fieldnames)
#             writer.writeheader()
#             writer.writerows(invalid_rows)
#         print(f"Invalid rows saved to {invalid_rows_file}")

#     return coordinates

# # Calculate only road distance, mark unreachable if fails
# def calculate_road_distance_only(coord1, coord2):
#     global quota_exceeded
#     snapped1 = snap_to_nearest(coord1)
#     snapped2 = snap_to_nearest(coord2)

#     if not snapped1 or not snapped2:
#         print("One or both points not routable, marking unreachable.")
#         return "Unreachable"

#     try:
#         result = client.directions([snapped1, snapped2])
#         distance_m = result['routes'][0]['summary']['distance']
#         print(f"Road distance: {distance_m/1000:.2f} km")
#         return round(distance_m / 1000, 2)
#     except openrouteservice.exceptions.ApiError as e:
#         if "Quota exceeded" in str(e):
#             print("Quota exceeded! Stopping calculations.")
#             quota_exceeded = True
#         print(f"Routing API Error: {e}")
#     except Exception as e:
#         print(f"Unexpected routing error: {e}")

#     return "Unreachable"

# # Write results to CSV
# def write_results_to_csv(output_file, results):
#     file_exists = os.path.exists(output_file)
#     with open(output_file, 'a', newline='') as file:
#         writer = csv.writer(file)
#         if not file_exists:
#             writer.writerow([
#                 'Source RefNo', 'Source Latitude', 'Source Longitude', 'Source Address',
#                 'Destination RefNo', 'Destination Latitude', 'Destination Longitude', 'Destination Address',
#                 'Distance (km)'
#             ])
#         writer.writerows(results)

# # Batch processing
# def process_batches(source_coords, destination_coords, output_file):
#     global quota_exceeded
#     results = []
#     if not os.path.exists(output_file):
#         with open(output_file, 'w', newline='') as file:
#             writer = csv.writer(file)
#             writer.writerow([
#                 'Source RefNo', 'Source Latitude', 'Source Longitude', 'Source Address',
#                 'Destination RefNo', 'Destination Latitude', 'Destination Longitude', 'Destination Address',
#                 'Distance (km)'
#             ])

#     for i in range(0, len(source_coords), BATCH_SIZE):
#         for j in range(0, len(destination_coords), BATCH_SIZE):
#             batch_results = []
#             for coord1 in source_coords[i:i+BATCH_SIZE]:
#                 for coord2 in destination_coords[j:j+BATCH_SIZE]:
#                     if quota_exceeded:
#                         return results
#                     distance = calculate_road_distance_only(coord1['coordinates'], coord2['coordinates'])
#                     batch_results.append([
#                         coord1['refno'], coord1['lat'], coord1['lon'], coord1['address'],
#                         coord2['refno'], coord2['lat'], coord2['lon'], coord2['address'],
#                         distance
#                     ])
#             results.extend(batch_results)
#             write_results_to_csv(output_file, batch_results)
#             time.sleep(1)
#     return results

# # Routes
# @app.route("/")
# def index():
#     return render_template("index.html")

# @app.route("/calculate", methods=["POST"])
# def calculate():
#     global quota_exceeded
#     quota_exceeded = False

#     source_file = request.files.get("source_csv")
#     destination_file = request.files.get("destination_csv")

#     if not source_file or not destination_file:
#         return "Source or destination file missing", 400

#     source_path = os.path.join("uploads", source_file.filename)
#     destination_path = os.path.join("uploads", destination_file.filename)
#     source_file.save(source_path)
#     destination_file.save(destination_path)

#     invalid_source_file = os.path.join(app.config['OUTPUT_FOLDER'], "invalid_source_rows.csv")
#     invalid_destination_file = os.path.join(app.config['OUTPUT_FOLDER'], "invalid_destination_rows.csv")

#     source_coords = read_coordinates_from_csv(source_path, invalid_source_file)
#     destination_coords = read_coordinates_from_csv(destination_path, invalid_destination_file)

#     output_file_name = "road_distances_output.csv"
#     output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], output_file_name)

#     process_batches(source_coords, destination_coords, output_file_path)

#     return render_template("result.html",
#                            output_file=output_file_name,
#                            quota_exceeded=quota_exceeded,
#                            invalid_source_file="invalid_source_rows.csv",
#                            invalid_destination_file="invalid_destination_rows.csv",
#                            status="Complete" if not quota_exceeded else "Partially Complete")

# @app.route('/download/<filename>')
# def download_file(filename):
#     file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
#     if os.path.exists(file_path):
#         return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)
#     return f"File '{filename}' not found.", 404

# if __name__ == "__main__":
#     app.run(debug=True, port=5000)



from flask import Flask, render_template, request, send_from_directory
import os
import csv
import openrouteservice
import requests
import time

app = Flask(__name__)

app.config['OUTPUT_FOLDER'] = os.path.join(os.getcwd(), 'outputs')
os.makedirs("uploads", exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

API_KEY = "YOUR_VALID_API_KEY"  # Replace with your correct API key
BATCH_SIZE = 40
quota_exceeded = False

# Read coordinates from CSV
def read_coordinates_from_csv(file_path, invalid_rows_file):
    coordinates = []
    invalid_rows = []

    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                lat = float(row['Latitude'].strip().rstrip(','))
                lon = float(row['Longitude'].strip().rstrip(','))

                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    raise ValueError("Coordinates out of range")

                coordinates.append({
                    'lat': lat,
                    'lon': lon,
                    'refno': row['RefNo'],
                    'address': row['Address'],
                    'coordinates': (lon, lat)
                })

            except Exception as e:
                print(f"Invalid row: {row} - {e}")
                invalid_rows.append(row)

    if invalid_rows:
        with open(invalid_rows_file, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(invalid_rows)
        print(f"Invalid rows written to {invalid_rows_file}")

    print(f"Total valid coordinates: {len(coordinates)}")
    return coordinates

# Snap coordinates to nearest road
def snap_to_road(api_key, lon, lat):
    url = "https://api.openrouteservice.org/v2/snap/driving-car"
    headers = {'Authorization': api_key, 'Content-Type': 'application/json'}
    body = {"locations": [[lon, lat]]}

    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

        if data and 'snapped_points' in data and data['snapped_points']:
            snapped_location = data['snapped_points'][0]['location']
            print(f"Snapped ({lon}, {lat}) to {snapped_location}")
            return {'location': snapped_location}
        else:
            print(f"No snapped location for ({lon}, {lat})")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Failed to snap ({lon}, {lat}): {e}")
        return None

# Calculate road distance with unreachable handling
def calculate_road_distance(api_key, coord1, coord2):
    client = openrouteservice.Client(key=api_key)

    snapped_src = snap_to_road(api_key, coord1[0], coord1[1])
    snapped_dst = snap_to_road(api_key, coord2[0], coord2[1])

    if not snapped_src or not snapped_dst:
        print("One or both points not routable, marking unreachable.")
        return None

    try:
        route = client.directions([snapped_src['location'], snapped_dst['location']])
        distance_m = route['routes'][0]['summary']['distance']
        return distance_m / 1000
    except openrouteservice.exceptions.ApiError as e:
        print(f"API Error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
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
        writer.writerows(results)

# Batch processing
def process_batches(source_coords, destination_coords, api_key, output_file):
    global quota_exceeded
    results = []

    if not os.path.exists(output_file):
        with open(output_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                'Source RefNo', 'Source Latitude', 'Source Longitude', 'Source Address',
                'Destination RefNo', 'Destination Latitude', 'Destination Longitude', 'Destination Address',
                'Distance (km)'
            ])

    for i in range(0, len(source_coords), BATCH_SIZE):
        for j in range(0, len(destination_coords), BATCH_SIZE):
            batch_results = []
            for src in source_coords[i:i+BATCH_SIZE]:
                for dst in destination_coords[j:j+BATCH_SIZE]:
                    if quota_exceeded:
                        return results

                    distance = calculate_road_distance(api_key, src['coordinates'], dst['coordinates'])
                    if distance is not None:
                        batch_results.append([
                            src['refno'], src['lat'], src['lon'], src['address'],
                            dst['refno'], dst['lat'], dst['lon'], dst['address'],
                            round(distance, 2)
                        ])
            results.extend(batch_results)
            write_results_to_csv(output_file, batch_results)
            time.sleep(1)

    return results

# Routes
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

    process_batches(source_coords, destination_coords, API_KEY, output_file_path)

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
    try:
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        if os.path.exists(file_path):
            return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)
        else:
            return f"File '{filename}' not found.", 404
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
