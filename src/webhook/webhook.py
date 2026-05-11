from flask import Flask, request
from worker import scan_task

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle():
    try:
        event = request.json
        if not event or "Records" not in event:
            return "OK", 200 # Return 200 even for pings to keep MinIO happy

	for record in event["Records"]
            bucket = record["s3"]["bucket"]["name"]
            key = record["s3"]["object"]["key"]

            # Push the task to the Redis queue asynchronously
            scan_task.delay(bucket, key)
            print(f"[QUEUED] {bucket}/{key}")
        
        # Instantly return success to MinIO
        return "Accepeted", 202 #202 Accepeted is more accurate for async tasks

    except Exception as e:
        print(f"[ERROR] API failed to queue: {e}")
        return "Internal Error", 500
