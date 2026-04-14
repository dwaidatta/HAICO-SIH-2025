"""
app.py — Flask backend with logging + richer status endpoint
"""

from dotenv import load_dotenv
load_dotenv()

import logging
import os
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_file, render_template

import ai_enhancer
import obfuscator
import report as report_builder
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = config.UPLOAD_FOLDER
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _set_status(job_id: str, status: str, detail: str = ""):
    with _jobs_lock:
        _jobs[job_id]["status"] = status
        _jobs[job_id]["detail"] = detail
    logger.info("Job %s  ->  %s  %s", job_id[:8], status, detail)


def _allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in config.ALLOWED_EXTS


def _run_pipeline(job_id: str, src_path: str, filename: str, passes: str):
    job_dir = str(Path(config.UPLOAD_FOLDER) / job_id)

    try:
        # 1. AI Enhancement
        _set_status(job_id, "ai_enhancing", "Sending source to Gemini...")

        with open(src_path, "r", errors="replace") as f:
            original_source = f.read()

        ai_result = ai_enhancer.enhance(original_source, filename)

        if ai_result["error"]:
            logger.warning("AI enhancement failed for job %s: %s",
                           job_id[:8], ai_result["error"])
            _set_status(job_id, "ai_enhancing",
                        f"AI failed ({ai_result['error'][:80]}), using original source")
        else:
            _set_status(job_id, "ai_enhancing", "Gemini returned enhanced source")

        enhanced_path = str(Path(job_dir) / f"enhanced_{filename}")
        with open(enhanced_path, "w") as f:
            f.write(ai_result["enhanced_source"])

        # 2. Compilation
        _set_status(job_id, "compiling", "Running Polaris clang...")

        obfu_result = obfuscator.run_pipeline(
            src=enhanced_path,
            job_dir=job_dir,
            passes=passes,
        )

        if obfu_result.get("error"):
            _set_status(job_id, "error", obfu_result["error"][:120])
            with _jobs_lock:
                _jobs[job_id]["report"] = report_builder.build(
                    ai_result=ai_result,
                    obfu_result=obfu_result,
                    original_filename=filename,
                    passes_used=passes or config.DEFAULT_PASSES,
                )
            return

        # 3. Report
        final_report = report_builder.build(
            ai_result=ai_result,
            obfu_result=obfu_result,
            original_filename=filename,
            passes_used=passes or config.DEFAULT_PASSES,
        )

        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["detail"] = "Pipeline complete"
            _jobs[job_id]["report"] = final_report

        logger.info("Job %s done — verdict=%s", job_id[:8], final_report.get("verdict"))

    except Exception as exc:
        logger.exception("Unhandled exception in pipeline for job %s", job_id[:8])
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["detail"] = str(exc)
            _jobs[job_id]["report"] = {
                "verdict": "ERROR",
                "error":   str(exc),
            }


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/upload")
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    f = request.files["file"]
    if not f.filename or not _allowed(f.filename):
        return jsonify({"error": "Only .c and .cpp files are accepted"}), 400

    passes  = request.form.get("passes", "").strip()
    job_id  = uuid.uuid4().hex
    job_dir = Path(config.UPLOAD_FOLDER) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    src_path = str(job_dir / f.filename)
    f.save(src_path)
    logger.info("Uploaded %s -> job %s  passes=%s", f.filename, job_id[:8], passes)

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "detail": "Job created", "report": None}

    t = threading.Thread(
        target=_run_pipeline,
        args=(job_id, src_path, f.filename, passes),
        daemon=True,
    )
    t.start()
    return jsonify({"job_id": job_id}), 202


@app.get("/status/<job_id>")
def status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "job_id": job_id,
        "status": job["status"],
        "detail": job.get("detail", ""),
    })


@app.get("/report/<job_id>")
def get_report(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] not in ("done", "error"):
        return jsonify({"error": "Report not ready yet", "status": job["status"]}), 202
    return jsonify(job["report"])


@app.get("/download/<job_id>")
def download(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] != "done":
        return jsonify({"error": "Not ready"}), 202
    obfu_bin = Path(config.UPLOAD_FOLDER) / job_id / "obfu_out"
    if not obfu_bin.exists():
        return jsonify({"error": "Binary not found"}), 404
    return send_file(
        str(obfu_bin),
        as_attachment=True,
        download_name="obfuscated_binary",
        mimetype="application/octet-stream",
    )


if __name__ == "__main__":
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        use_reloader=False,
    )