import os
import subprocess
import shutil
import difflib
from flask import Flask, request, jsonify, render_template, send_file
import google.generativeai as genai

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(__file__), 'output')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
genai.configure(api_key=GEMINI_API_KEY)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

ALLOWED = {'.c', '.cpp', '.cc', '.cxx'}


# ── Step 1: AI junk injection ──────────────────────────────────────────────
def ai_inject_junk(source_code: str, language: str) -> str:
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""You are a code obfuscation assistant. Inject confusing but completely
non-functional junk code into the following {language} source. Rules:
1. Add at least 3 dead loops: while(0){{...}} or if(false){{...}}
2. Add at least 5 meaningless variables (random-looking names) that are never used.
3. Add at least 2 functions that are defined but NEVER called.
4. Do NOT alter the actual logic, inputs, or outputs of the program in any way.
5. Return ONLY the modified source code. No markdown fences, no explanations.

Original code:
{source_code}"""
    response = model.generate_content(prompt)
    return response.text.strip()


# ── Step 2: Polaris obfuscator ─────────────────────────────────────────────
def run_polaris(input_path: str, output_path: str) -> tuple[bool, str]:
    """
    Shells out to the `polaris` binary.
    If Polaris is not installed → demo mode (AI output used directly).
    Adjust the command/flags to match your Polaris build.
    """
    try:
        result = subprocess.run(
            ["polaris", "-i", input_path, "-o", output_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return True, result.stdout or "Polaris completed successfully."
        return False, result.stderr
    except FileNotFoundError:
        shutil.copy(input_path, output_path)
        return True, "[DEMO MODE] Polaris not installed — AI-modified code used as obfuscated output."
    except subprocess.TimeoutExpired:
        return False, "Polaris obfuscator timed out (30s)."


# ── Step 3: Compilation ────────────────────────────────────────────────────
def compile_source(source_path: str, out_dir: str, base: str, language: str) -> dict:
    results = {}
    compiler    = "g++"                    if language == "cpp" else "gcc"
    win_compiler = "x86_64-w64-mingw32-g++" if language == "cpp" else "x86_64-w64-mingw32-gcc"

    # Linux native binary
    bin_path = os.path.join(out_dir, base + ".bin")
    try:
        r = subprocess.run([compiler, source_path, "-o", bin_path, "-O0"],
                           capture_output=True, text=True, timeout=30)
        results["bin"] = {
            "path": bin_path if r.returncode == 0 else None,
            "success": r.returncode == 0,
            "log": r.stderr or r.stdout,
        }
    except FileNotFoundError:
        results["bin"] = {"path": None, "success": False,
                          "log": f"{compiler} not found. Run: sudo apt install build-essential"}
    except subprocess.TimeoutExpired:
        results["bin"] = {"path": None, "success": False, "log": "Compilation timed out."}

    # Windows EXE via MinGW
    exe_path = os.path.join(out_dir, base + ".exe")
    try:
        r = subprocess.run([win_compiler, source_path, "-o", exe_path, "-O0", "-static"],
                           capture_output=True, text=True, timeout=30)
        results["exe"] = {
            "path": exe_path if r.returncode == 0 else None,
            "success": r.returncode == 0,
            "log": r.stderr or r.stdout,
        }
    except FileNotFoundError:
        results["exe"] = {"path": None, "success": False,
                          "log": f"{win_compiler} not found. Run: sudo apt install mingw-w64"}
    except subprocess.TimeoutExpired:
        results["exe"] = {"path": None, "success": False, "log": "Cross-compilation timed out."}

    return results


# ── Step 4: Comparison report ──────────────────────────────────────────────
def build_report(original: str, ai_code: str, obfuscated: str) -> dict:
    def stats(code):
        lines = code.splitlines()
        return {"lines": len(lines), "chars": len(code),
                "blank_lines": sum(1 for l in lines if not l.strip())}

    def udiff(a, b):
        return list(difflib.unified_diff(
            a.splitlines(keepends=True),
            b.splitlines(keepends=True),
            lineterm=""
        ))[:300]

    return {
        "original_stats":    stats(original),
        "ai_modified_stats": stats(ai_code),
        "obfuscated_stats":  stats(obfuscated),
        "original_vs_ai_diff":   udiff(original, ai_code),
        "ai_vs_obfuscated_diff": udiff(ai_code, obfuscated),
        "original_snippet":   original[:3000],
        "ai_snippet":         ai_code[:3000],
        "obfuscated_snippet": obfuscated[:3000],
    }


# ── Routes ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/obfuscate", methods=["POST"])
def obfuscate():
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    f        = request.files["file"]
    filename = f.filename or "source.c"
    ext      = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED:
        return jsonify({"error": "Only .c / .cpp files are accepted."}), 400

    language = "cpp" if ext in (".cpp", ".cc", ".cxx") else "c"
    base     = os.path.splitext(filename)[0]

    # Save original
    orig_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    f.save(orig_path)
    with open(orig_path, "r", encoding="utf-8", errors="replace") as fh:
        original_code = fh.read()

    # Step 1 — AI injection
    try:
        ai_code = ai_inject_junk(original_code, language)
    except Exception as e:
        return jsonify({"error": f"AI step failed: {e}"}), 500

    ai_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base}_ai{ext}")
    with open(ai_path, "w", encoding="utf-8") as fh:
        fh.write(ai_code)

    # Step 2 — Polaris
    obf_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{base}_obfuscated{ext}")
    ok, polaris_log = run_polaris(ai_path, obf_path)
    if not ok:
        return jsonify({"error": f"Polaris failed: {polaris_log}"}), 500

    with open(obf_path, "r", encoding="utf-8", errors="replace") as fh:
        obfuscated_code = fh.read()

    # Step 3 — Compile
    compile_res = compile_source(obf_path, app.config['OUTPUT_FOLDER'], base, language)

    # Step 4 — Report
    report = build_report(original_code, ai_code, obfuscated_code)

    return render_template("index.html",
        report=report,
        polaris_log=polaris_log,
        compile={
            "bin": {
                "success": compile_res["bin"]["success"],
                "log": compile_res["bin"]["log"],
                "download": f"/download/{base}.bin" if compile_res["bin"]["success"] else None,
            },
            "exe": {
                "success": compile_res["exe"]["success"],
                "log": compile_res["exe"]["log"],
                "download": f"/download/{base}.exe" if compile_res["exe"]["success"] else None,
            },
        }
    )


@app.route("/download/<path:filename>")
def download(filename):
    safe = os.path.basename(filename)
    path = os.path.join(app.config['OUTPUT_FOLDER'], safe)
    if not os.path.isfile(path):
        return jsonify({"error": "File not found."}), 404
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)