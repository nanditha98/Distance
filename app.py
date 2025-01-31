
from flask import Flask, render_template, request, send_from_directory
import os
import csv
import openrouteservice
import time

# Initialize Flask app
app = Flask(__name__)

# Set the output folder path for downloaded files
app.config['OUTPUT_FOLDER'] = os.path.join(os.getcwd(), 'outputs')

# Create required directories if not present
os.makedirs("uploads", exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# OpenRouteService API key
API_KEY = "5b3ce3597851110001cf62484f471217e61b471d912e663ef4591a19"

# Batch size (Max API rate limit)
BATCH_SIZE = 40

# Quota exceeded flag
quota_exceeded = False

# Read coordinates from CSV and track invalid rows with validations
def read_coordinates_from_csv(file_path, invalid_rows_file):
    coordinates = []
    invalid_rows = []

    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                # Validate latitude and longitude format
                lat = float(row['Latitude'].strip())
                lon = float(row['Longitude'].strip())

                # Validate latitude and longitude range
                if not (-90 <= lat <= 90):
                    raise ValueError(f"Latitude {lat} out of range")
                if not (-180 <= lon <= 180):
                    raise ValueError(f"Longitude {lon} out of range")
                
                # Add the valid coordinates along with RefNo (no change to RefNo)
                coordinates.append({
                    'lat': lat,
                    'lon': lon,
                    'refno': row['refno'],  # Directly use the RefNo from the CSV
                    'coordinates': (lon, lat)  # OpenRouteService requires (lon, lat) format
                })

            except ValueError as e:
                print(f"Invalid row detected: {row} - Error: {e}")
                invalid_rows.append(row)

        print(f"Number of invalid rows: {len(invalid_rows)}")

    # Write invalid rows to a CSV file
    if invalid_rows:
        print(f"Writing invalid rows to {invalid_rows_file}")
        with open(invalid_rows_file, 'w', newline='') as invalid_file:
            writer = csv.DictWriter(invalid_file, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(invalid_rows)
        print(f"Invalid rows saved to {invalid_rows_file}")

    return coordinates

# Calculate road distance using OpenRouteService
def calculate_road_distance(api_key, coord1, coord2):
    global quota_exceeded
    client = openrouteservice.Client(key=api_key)
    coords = [coord1, coord2]
    try:
        result = client.directions(coords)
        distance_m = result['routes'][0]['summary']['distance']
        return distance_m / 1000  # Convert meters to kilometers
    except openrouteservice.exceptions.ApiError as e:
        if "Quota exceeded" in str(e):
            print("Quota exceeded! Stopping calculations.")
            quota_exceeded = True
        return None
    except Exception as e:
        print(f"Error calculating distance: {e}")
        return None

# Write results to CSV with 'RefNo' for both source and destination
def write_results_to_csv(output_file, results):
    file_exists = os.path.exists(output_file)
    with open(output_file, 'a', newline='') as file:
        writer = csv.writer(file)
        # Write headers only if file doesn't exist
        if not file_exists:
            writer.writerow(['Source RefNo', 'Source Latitude', 'Source Longitude', 'Destination RefNo', 'Destination Latitude', 'Destination Longitude', 'Distance (km)'])
        
        # Write the rows with 'RefNo' for both source and destination
        for result in results:
            writer.writerow(result)

# Process distances in batches with 'RefNo' for both source and destination
def process_batches(source_coords, destination_coords, api_key, output_file):
    global quota_exceeded
    results = []
    if not os.path.exists(output_file):  # Ensure the file exists
        with open(output_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Source RefNo', 'Source Latitude', 'Source Longitude', 'Destination RefNo', 'Destination Latitude', 'Destination Longitude', 'Distance (km)'])

    for i in range(0, len(source_coords), BATCH_SIZE):
        for j in range(0, len(destination_coords), BATCH_SIZE):
            batch_results = []
            for coord1 in source_coords[i:i + BATCH_SIZE]:
                for coord2 in destination_coords[j:j + BATCH_SIZE]:
                    if quota_exceeded:
                        return results  # Stop processing if quota is exceeded
                    distance = calculate_road_distance(api_key, coord1['coordinates'], coord2['coordinates'])
                    if distance is not None:
                        # Include the RefNo from source and destination
                        batch_results.append([coord1['refno'], coord1['lat'], coord1['lon'], coord2['refno'], coord2['lat'], coord2['lon'], round(distance, 2)])
            results.extend(batch_results)
            write_results_to_csv(output_file, batch_results)
            time.sleep(1)  # Add a delay to avoid hitting API rate limits
    return results

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/calculate", methods=["POST"])
def calculate():
    global quota_exceeded
    quota_exceeded = False  # Reset the flag before starting processing

    # Ensure both files are provided
    if "source_csv" not in request.files or "destination_csv" not in request.files:
        return "Source or destination file missing", 400

    # Get the uploaded files
    source_file = request.files["source_csv"]
    destination_file = request.files["destination_csv"]

    # Check for empty filenames
    if source_file.filename == "" or destination_file.filename == "":
        return "One or both files are empty", 400

    # Save uploaded files
    source_path = os.path.join("uploads", source_file.filename)
    destination_path = os.path.join("uploads", destination_file.filename)
    source_file.save(source_path)
    destination_file.save(destination_path)

    # File for invalid rows
    invalid_source_file = os.path.join(app.config['OUTPUT_FOLDER'], "invalid_source_rows.csv")
    invalid_destination_file = os.path.join(app.config['OUTPUT_FOLDER'], "invalid_destination_rows.csv")
    print("invalid", invalid_source_file)
    print("invaild", invalid_destination_file)

    # Read coordinates from the uploaded CSVs
    source_coords = read_coordinates_from_csv(source_path, invalid_source_file)
    destination_coords = read_coordinates_from_csv(destination_path, invalid_destination_file)

    # Output file
    output_file_name = "road_distances_output.csv"
    output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], output_file_name)

    # Process distances and write to output file
    process_batches(source_coords, destination_coords, API_KEY, output_file_path)

    # Pass the `quota_exceeded` flag, output file name, and invalid row files to the template
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
        # Get the path of the output file
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        
        # Check if file exists
        if os.path.exists(file_path):
            print(f"File available for download: {file_path}")
            return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)
        else:
            print(f"File not found: {file_path}")
            return f"File '{filename}' not found.", 404
    except Exception as e:
        print(f"Error in file download: {str(e)}")
        return f"Error: {str(e)}", 500

if __name__ == "__main__":
    app.run(debug=True, use_debugger=False,port=0)
