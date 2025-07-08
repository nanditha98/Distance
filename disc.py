from flask import Flask, render_template, request, send_from_directory
import os
import csv
import openrouteservice
import time

# ──────────────────────────────────────────────────────────────────────────────
# Flask setup
# ──────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['OUTPUT_FOLDER'] = os.path.join(os.getcwd(), 'outputs')

os.makedirs("uploads",               exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────
API_KEY      = "5b3ce3597851110001cf6248242930a613eb44fba576aa3429a6f74b"
BATCH_SIZE   = 40            # obey ORS rate‑limit
quota_exceeded = False       # global flag

# ──────────────────────────────────────────────────────────────────────────────
# Helper: read & validate one CSV (quotes removed, commas neutralised)
# ──────────────────────────────────────────────────────────────────────────────
def read_coordinates_from_csv(file_path: str, invalid_rows_file: str):
    """
    Returns a list of dicts:
        {lat, lon, refno, address, coordinates}
    – Removes surrounding " quotes in Address
    – Replaces commas inside Address with spaces (so writer never re‑quotes)
    """
    coordinates, invalid_rows = [], []

    with open(file_path, "r", encoding="utf‑8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row["Latitude"].strip())
                lon = float(row["Longitude"].strip())

                if not (-90  <= lat <= 90):
                    raise ValueError(f"Latitude {lat} out of range")
                if not (-180 <= lon <= 180):
                    raise ValueError(f"Longitude {lon} out of range")

                cleaned_address = (
                    row["Address"]
                    .strip()          # trim spaces
                    .strip('"')       # strip leading / trailing "
                    .replace(",", " ")  # neutralise commas so no quoting later
                )

                coordinates.append(
                    dict(
                        lat=lat,
                        lon=lon,
                        refno=row["RefNo"].strip(),
                        address=cleaned_address,
                        coordinates=(lon, lat),   # ORS wants (lon, lat)
                    )
                )

            except ValueError as e:
                print(f"Invalid row skipped → {row}  ·  {e}")
                invalid_rows.append(row)

    # persist invalid rows for user download
    if invalid_rows:
        with open(invalid_rows_file, "w", newline="", encoding="utf‑8") as bad:
            writer = csv.DictWriter(bad, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(invalid_rows)
        print(f"✘ {len(invalid_rows)} invalid rows written to {invalid_rows_file}")

    return coordinates

# ──────────────────────────────────────────────────────────────────────────────
# Distance calculation (ORS)
# ──────────────────────────────────────────────────────────────────────────────
def calculate_road_distance(api_key, coord1, coord2):
    global quota_exceeded
    client = openrouteservice.Client(key=api_key)
    try:
        result = client.directions([coord1, coord2])
        dist_km = result["routes"][0]["summary"]["distance"] / 1000
        return round(dist_km, 2)
    except openrouteservice.exceptions.ApiError as e:
        if "Quota exceeded" in str(e):
            quota_exceeded = True
            print("→ ORS quota exceeded – halting further calls")
        else:
            print(f"ORS ApiError {coord1}->{coord2} · {e}")
        return None
    except Exception as e:
        print(f"Unexpected error {coord1}->{coord2} · {e}")
        return None

# ──────────────────────────────────────────────────────────────────────────────
# CSV writer (result file)
# ──────────────────────────────────────────────────────────────────────────────
RESULT_HEADER = [
    "Source RefNo", "Source Latitude", "Source Longitude", "Source Address",
    "Destination RefNo", "Destination Latitude", "Destination Longitude",
    "Destination Address", "Distance (km)"
]

def write_results_to_csv(output_file, rows):
    file_exists = os.path.exists(output_file)
    with open(output_file, "a", newline="", encoding="utf‑8") as f:
        writer = csv.writer(
            f,
            quoting=csv.QUOTE_NONE,   # we stripped commas, so no quotes needed
            escapechar="\\",
        )
        if not file_exists:
            writer.writerow(RESULT_HEADER)
        writer.writerows(rows)

# ──────────────────────────────────────────────────────────────────────────────
# Batch processor
# ──────────────────────────────────────────────────────────────────────────────
def process_batches(source, dest, api_key, output_file):
    if not os.path.exists(output_file):
        with open(output_file, "w", newline="", encoding="utf‑8") as f:
            csv.writer(f, quoting=csv.QUOTE_NONE, escapechar="\\").writerow(RESULT_HEADER)

    for i in range(0, len(source), BATCH_SIZE):
        for j in range(0, len(dest), BATCH_SIZE):
            batch_rows = []
            for s in source[i : i + BATCH_SIZE]:
                for d in dest[j : j + BATCH_SIZE]:
                    if quota_exceeded:
                        return  # hard stop
                    km = calculate_road_distance(api_key, s["coordinates"], d["coordinates"])
                    if km is not None:
                        batch_rows.append(
                            [
                                s["refno"], s["lat"], s["lon"], s["address"],
                                d["refno"], d["lat"], d["lon"], d["address"],
                                 round(km, 2)
                              
                              
                            ]
                        )
            write_results_to_csv(output_file, batch_rows)
            time.sleep(1)  # gentle on ORS

# ──────────────────────────────────────────────────────────────────────────────
# Flask routes
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/calculate", methods=["POST"])
def calculate():
    global quota_exceeded
    quota_exceeded = False

    if "source_csv" not in request.files or "destination_csv" not in request.files:
        return "Source or destination file missing", 400

    src_file = request.files["source_csv"]
    dst_file = request.files["destination_csv"]
    if src_file.filename == "" or dst_file.filename == "":
        return "One or both files are empty", 400

    src_path = os.path.join("uploads", src_file.filename)
    dst_path = os.path.join("uploads", dst_file.filename)
    src_file.save(src_path)
    dst_file.save(dst_path)

    # paths for invalid‑row logs
    bad_src = os.path.join(app.config["OUTPUT_FOLDER"], "invalid_source_rows.csv")
    bad_dst = os.path.join(app.config["OUTPUT_FOLDER"], "invalid_destination_rows.csv")

    src_coords = read_coordinates_from_csv(src_path, bad_src)
    dst_coords = read_coordinates_from_csv(dst_path, bad_dst)

    output_name = "road_distances_output.csv"
    output_path = os.path.join(app.config["OUTPUT_FOLDER"], output_name)

    process_batches(src_coords, dst_coords, API_KEY, output_path)

    return render_template(
        "result.html",
        output_file=output_name,
        quota_exceeded=quota_exceeded,
        invalid_source_file=os.path.basename(bad_src),
        invalid_destination_file=os.path.basename(bad_dst),
        status="Complete" if not quota_exceeded else "Partially Complete",
    )

@app.route("/download/<filename>")
def download_file(filename):
    path = os.path.join(app.config["OUTPUT_FOLDER"], filename)
    if not os.path.exists(path):
        return f"File '{filename}' not found.", 404
    return send_from_directory(app.config["OUTPUT_FOLDER"], filename, as_attachment=True)

# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # debug=True but disable reloader so port 0 binding works in some IDEs
    app.run(debug=True, use_reloader=False, port=0)
