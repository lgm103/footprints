import os
import time
import socket
import psutil
import uuid
import json
from celery import Celery
from minio import Minio

# Point Celery at the internal Kubernetes Redis service
celery_app = Celery('worker', broker='redis://redis:6379/0')

celery_app.conf.update(
    # 1. Disable prefetching: Take only one task at a time.
    # This prevents one pod from "hoarding" tasks if it's slow.
    worker_prefetch_multiplier=1,
    
    # 2. Late Acknowledgement: Only tell Redis the task is 'done' 
    # AFTER the function finishes. If the pod crashes, the task goes back to the queue.
    task_acks_late=True,
    
    # 3. Task Timeout: Hard kill the task if it takes longer than 60s
    task_time_limit=60
)

minio_client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False
)

def scan_file(path):
    s = socket.socket()
    # PREVENT DEADLOCKS: If ClamAV takes longer than 30 seconds, abort the thread
    s.settimeout(30.0) 
    
    try:
        s.connect(("clamav", 3310))
        s.sendall(b"zINSTREAM\0")

        with open(path, "rb") as f:
            while chunk := f.read(2048):
                size = len(chunk).to_bytes(4, byteorder="big")
                s.sendall(size + chunk)

        s.sendall((0).to_bytes(4, byteorder="big"))
        result = s.recv(1024)
        return result.decode()
    finally:
        s.close()

@celery_app.task
def scan_task(bucket, key):
    start = time.time()
    unique_id = uuid.uuid4().hex
    local_path = f"/tmp/{unique_id}_{key.replace('/', '_')}"
    print(f"[1/4] Starting task: {key}") # Trace point 1

    try:
        # 1. Download
        print(f"[2/4] Downloading {key}...")
        minio_client.fget_object(bucket, key, local_path)

        # 2. Scan
        print(f"[3/4] Streaming {key} to ClamAV...")
        scan_result = scan_file(local_path)
        infected = "FOUND" in scan_result

        print(f"[4/4] Scan complete for {key}: {scan_result.strip()}")
        # 3. Quarantine
        if infected:
            minio_client.fput_object("quarantined", key, local_path)
            minio_client.remove_object(bucket, key)

        duration = time.time() - start
        
        log = {
            "bucket": bucket,
            "object": key,
            "infected": infected,
            "scan_result": scan_result.strip(),
            "duration_sec": round(duration, 3)
        }
        print(json.dumps(log))

    except Exception as e:
        print(f"[ERROR] Task failed for {bucket}/{key}: {e}")
    finally:
        # 4. Guarantee Disk Cleanup
        if os.path.exists(local_path):
            os.remove(local_path)
