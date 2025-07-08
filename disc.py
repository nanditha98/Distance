from flask import Flask, render_template, request, send_from_directory
import os
import csv
import requests
import time

app = Flask(__name__)
app.config['OUTPUT_FOLDER'] = os.path.join(os.getcwd(), 'outputs')
os.makedirs("uploads", exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

BATCH_SIZE = 40

def reads_coordinates_from_csv(file_path, invalid_rows_file):
    coordinates = []
    invalid_rows = []

    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames

        for row in reader:
            try:
                if "Address" in row:
                    row["Address"] = row["Address"].strip().strip('"')

                lat = float(row['Latitude'].strip())
                lon = float(row['Longitude'].strip())

                if not (-90 <= lat <= 90):
                    raise ValueError(f"Latitude {lat} out of range")
                if not (-180 <= lon <= 180):
                    raise ValueError(f"Longitude {lon} out of range")

                coordinates.append({
                    'lat': lat,
                    'lon': lon,
                    'refno': str(int(float(row['RefNo']))),
                    'coordinates': (lon, lat)
                })
            except ValueError as e:
                print(f"Invalid row detected: {row} - Error: {e}")
                invalid_rows.append(row)

    if invalid_rows:
        print(f"Writing invalid rows to {invalid_rows_file}")
        with open(invalid_rows_file, 'w', newline='') as invalid_file:
            writer = csv.DictWriter(invalid_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(invalid_rows)

    return coordinates

def write_results_to_csv(output_file, results):
    file_exists = os.path.exists(output_file)
    with open(output_file, 'a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Source RefNo', 'Source Latitude', 'Source Longitude',
                             'Destination RefNo', 'Destination Latitude', 'Destination Longitude', 'Distance (km)'])
        for result in results:
            writer.writerow(result)

def process_batches(source_coords, destination_coords, output_file):
    if not os.path.exists(output_file):
        with open(output_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                'Source RefNo', 'Source Latitude', 'Source Longitude',
                'Destination RefNo', 'Destination Latitude', 'Destination Longitude',
                'Distance (km)'
            ])

    for source in source_coords:
        for j in range(0, len(destination_coords), BATCH_SIZE):
            dest_batch = destination_coords[j:j + BATCH_SIZE]
            all_coords = [source['coordinates']] + [d['coordinates'] for d in dest_batch]
            coords_param = ';'.join(f"{lon},{lat}" for lon, lat in all_coords)
            url = f"http://router.project-osrm.org/table/v1/driving/{coords_param}?sources=0&annotations=distance"

            try:
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()

                if data["code"] == "Ok":
                    distances = data["distances"][0]
                    batch_results = []
                    for dest, dist in zip(dest_batch, distances[1:]):
                        km = round(dist / 1000, 2) if dist is not None else -1
                        batch_results.append([
                            source['refno'], source['lat'], source['lon'],
                            dest['refno'], dest['lat'], dest['lon'],
                            km
                        ])
                        print(f"\u2705 Distance: {source['refno']} → {dest['refno']} = {km} km")
                    write_results_to_csv(output_file, batch_results)
                else:
                    print(f"⚠️ OSRM error response: {data}")
            except Exception as e:
                print(f"🚫 Error processing batch: {e}")

            time.sleep(1)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/calculate", methods=["POST"])
def calculate():
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

    print("Reading source CSV...")
    source_coords = reads_coordinates_from_csv(source_path, invalid_source_file)
    print(f"✅ Total valid source rows: {len(source_coords)}")

    print("Reading destination CSV...")
    destination_coords = reads_coordinates_from_csv(destination_path, invalid_destination_file)
    print(f"✅ Total valid destination rows: {len(destination_coords)}")

    output_file_name = "road_distances_output.csv"
    output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], output_file_name)

    process_batches(source_coords, destination_coords, output_file_path)

    return render_template(
        "result.html",
        output_file=output_file_name,
        quota_exceeded=False,
        invalid_source_file="invalid_source_rows.csv",
        invalid_destination_file="invalid_destination_rows.csv",
        status="Complete"
    )

@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
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
    app.run(debug=True, use_debugger=False, port=0)
