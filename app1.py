# from flask import Flask, render_template, request, send_from_directory
# import os
# import csv
# import requests
# import time

# app = Flask(__name__)
# app.config['OUTPUT_FOLDER'] = os.path.join(os.getcwd(), 'outputs')
# os.makedirs("uploads", exist_ok=True)
# os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# BATCH_SIZE = 40

# def reads_coordinates_from_csv(file_path, invalid_rows_file, max_rows=20):
#     coordinates = []
#     invalid_rows = []

#     with open(file_path, 'r') as file:
#         reader = csv.DictReader(file)
#         fieldnames = reader.fieldnames

#         for idx, row in enumerate(reader):
#             if idx >= max_rows:
#                 break

#             try:
#                 if "Address" in row:
#                     row["Address"] = row["Address"].strip().strip('"')

#                 lat = float(row['Latitude'].strip())
#                 lon = float(row['Longitude'].strip())

#                 if not (-90 <= lat <= 90):
#                     raise ValueError(f"Latitude {lat} out of range")
#                 if not (-180 <= lon <= 180):
#                     raise ValueError(f"Longitude {lon} out of range")

#                 coordinates.append({
#                     'lat': lat,
#                     'lon': lon,
#                     'refno': str(int(float(row['RefNo']))),
#                     'coordinates': (lon, lat)
#                 })
#             except ValueError as e:
#                 print(f"Invalid row detected: {row} - Error: {e}")
#                 invalid_rows.append(row)

#     if invalid_rows:
#         print(f"Writing invalid rows to {invalid_rows_file}")
#         with open(invalid_rows_file, 'w', newline='') as invalid_file:
#             writer = csv.DictWriter(invalid_file, fieldnames=fieldnames)
#             writer.writeheader()
#             writer.writerows(invalid_rows)

#     return coordinates

# def calculate_road_distance_osrm(coord1, coord2):
#     lon1, lat1 = coord1
#     lon2, lat2 = coord2
#     url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
#     try:
#         response = requests.get(url)
#         if response.status_code == 200:
#             data = response.json()
#             if data["code"] == "Ok":
#                 distance_m = data["routes"][0]["distance"]
#                 return distance_m / 1000
#         else:
#             print(f"OSRM HTTP error: {response.status_code}")
#     except Exception as e:
#         print(f"OSRM error: {e}")
#     return None

# def write_results_to_csv(output_file, results):
#     file_exists = os.path.exists(output_file)
#     with open(output_file, 'a', newline='') as file:
#         writer = csv.writer(file)
#         if not file_exists:
#             writer.writerow(['Source RefNo', 'Source Latitude', 'Source Longitude', 'Destination RefNo', 'Destination Latitude', 'Destination Longitude', 'Distance (km)'])
#         for result in results:
#             writer.writerow(result)

# def process_batches(source_coords, destination_coords, output_file):
#     results = []

#     if not os.path.exists(output_file):
#         with open(output_file, 'w', newline='') as file:
#             writer = csv.writer(file)
#             writer.writerow([
#                 'Source RefNo', 'Source Latitude', 'Source Longitude',
#                 'Destination RefNo', 'Destination Latitude', 'Destination Longitude',
#                 'Distance (km)'
#             ])

#     for i in range(0, len(source_coords), BATCH_SIZE):
#         for j in range(0, len(destination_coords), BATCH_SIZE):
#             batch_results = []
#             for coord1 in source_coords[i:i + BATCH_SIZE]:
#                 for coord2 in destination_coords[j:j + BATCH_SIZE]:
#                     print(f"\u27a1\ufe0f Calculating: {coord1['refno']} → {coord2['refno']}")
#                     distance = calculate_road_distance_osrm(coord1['coordinates'], coord2['coordinates'])

#                     if distance is None:
#                         print(f"\u274c Failed to calculate distance: {coord1['refno']} → {coord2['refno']}")
#                         distance = -1
#                     else:
#                         print(f"\u2705 Distance: {coord1['refno']} → {coord2['refno']} = {round(distance, 2)} km")

#                     batch_results.append([
#                         coord1['refno'], coord1['lat'], coord1['lon'],
#                         coord2['refno'], coord2['lat'], coord2['lon'],
#                         round(distance, 2) if distance != -1 else distance
#                     ])

#             results.extend(batch_results)
#             write_results_to_csv(output_file, batch_results)
#             time.sleep(1)

#     return results

# @app.route("/")
# def index():
#     return render_template("index.html")

# @app.route("/calculate", methods=["POST"])
# def calculate():
#     if "source_csv" not in request.files or "destination_csv" not in request.files:
#         return "Source or destination file missing", 400

#     source_file = request.files["source_csv"]
#     destination_file = request.files["destination_csv"]

#     if source_file.filename == "" or destination_file.filename == "":
#         return "One or both files are empty", 400

#     source_path = os.path.join("uploads", source_file.filename)
#     destination_path = os.path.join("uploads", destination_file.filename)
#     source_file.save(source_path)
#     destination_file.save(destination_path)

#     invalid_source_file = os.path.join(app.config['OUTPUT_FOLDER'], "invalid_source_rows.csv")
#     invalid_destination_file = os.path.join(app.config['OUTPUT_FOLDER'], "invalid_destination_rows.csv")

#     print("Reading source CSV...")
#     source_coords = reads_coordinates_from_csv(source_path, invalid_source_file)
#     print(f"✅ Total valid source rows: {len(source_coords)}")

#     print("Reading destination CSV (limit 20)...")
#     destination_coords = reads_coordinates_from_csv(destination_path, invalid_destination_file, max_rows=20)
#     print(f"✅ Total valid destination rows: {len(destination_coords)}")

#     output_file_name = "road_distances_output.csv"
#     output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], output_file_name)

#     process_batches(source_coords, destination_coords, output_file_path)

#     return render_template(
#         "result.html",
#         output_file=output_file_name,
#         quota_exceeded=False,
#         invalid_source_file="invalid_source_rows.csv",
#         invalid_destination_file="invalid_destination_rows.csv",
#         status="Complete"
#     )

# @app.route('/download/<filename>')
# def download_file(filename):
#     try:
#         file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
#         if os.path.exists(file_path):
#             print(f"File available for download: {file_path}")
#             return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)
#         else:
#             print(f"File not found: {file_path}")
#             return f"File '{filename}' not found.", 404
#     except Exception as e:
#         print(f"Error in file download: {str(e)}")
#         return f"Error: {str(e)}", 500

# if __name__ == "__main__":
#     app.run(debug=True, use_debugger=False, port=0)



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

def calculate_road_distance_osrm(coord1, coord2):
    lon1, lat1 = coord1
    lon2, lat2 = coord2
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data["code"] == "Ok":
                distance_m = data["routes"][0]["distance"]
                return distance_m / 1000
        else:
            print(f"OSRM HTTP error: {response.status_code}")
    except Exception as e:
        print(f"OSRM error: {e}")
    return None

def write_results_to_csv(output_file, results):
    file_exists = os.path.exists(output_file)
    with open(output_file, 'a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Source RefNo', 'Source Latitude', 'Source Longitude', 'Destination RefNo', 'Destination Latitude', 'Destination Longitude', 'Distance (km)'])
        for result in results:
            writer.writerow(result)

def process_batches(source_coords, destination_coords, output_file):
    results = []

    if not os.path.exists(output_file):
        with open(output_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                'Source RefNo', 'Source Latitude', 'Source Longitude',
                'Destination RefNo', 'Destination Latitude', 'Destination Longitude',
                'Distance (km)'
            ])

    for i in range(0, len(source_coords), BATCH_SIZE):
        for j in range(0, len(destination_coords), BATCH_SIZE):
            batch_results = []
            for coord1 in source_coords[i:i + BATCH_SIZE]:
                for coord2 in destination_coords[j:j + BATCH_SIZE]:
                    print(f"\u27a1\ufe0f Calculating: {coord1['refno']} → {coord2['refno']}")
                    distance = calculate_road_distance_osrm(coord1['coordinates'], coord2['coordinates'])

                    if distance is None:
                        print(f"\u274c Failed to calculate distance: {coord1['refno']} → {coord2['refno']}")
                        distance = -1
                    else:
                        print(f"\u2705 Distance: {coord1['refno']} → {coord2['refno']} = {round(distance, 2)} km")

                    batch_results.append([
                        coord1['refno'], coord1['lat'], coord1['lon'],
                        coord2['refno'], coord2['lat'], coord2['lon'],
                        round(distance, 2) if distance != -1 else distance
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
