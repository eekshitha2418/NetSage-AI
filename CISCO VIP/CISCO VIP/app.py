import http.server
import socketserver
import json
import os
import sys

PORT = 8000

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS for local development testing
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/results":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            results_path = "ai_diagnosis_results.json"
            # Self-healing: if the diagnosis results file doesn't exist, run the pipeline
            if not os.path.exists(results_path):
                print("[*] ai_diagnosis_results.json not found. Running diagnosis pipeline automatically...")
                from run_diagnosis import run_diagnoses
                run_diagnoses()

            try:
                with open(results_path, 'r', encoding='utf-8') as f:
                    results = json.load(f)
            except Exception as e:
                results = []
                print(f"[-] Error reading {results_path}: {e}")

            # Load the human review database
            review_path = "human_review_log.json"
            reviews = {}
            if os.path.exists(review_path):
                try:
                    with open(review_path, 'r', encoding='utf-8') as f:
                        reviews = json.load(f)
                except Exception as e:
                    print(f"[-] Error reading {review_path}: {e}")

            # Merge the human review status into each diagnosis case
            for case in results:
                case_id_str = str(case.get("case_id"))
                if case_id_str in reviews:
                    case["human_review"] = reviews[case_id_str]
                else:
                    case["human_review"] = {
                        "status": "Unreviewed",
                        "reviewer_notes": "",
                        "corrected_fix_steps": ""
                    }

            self.wfile.write(json.dumps(results, indent=4).encode('utf-8'))
        else:
            # Fallback to serve static web files
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/review":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                case_id = str(data.get("case_id"))
                status = data.get("status")
                reviewer_notes = data.get("reviewer_notes", "")
                corrected_fix_steps = data.get("corrected_fix_steps", "")

                if not case_id or not status:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Missing case_id or status"}).encode('utf-8'))
                    return

                # Load and update the human review database
                review_path = "human_review_log.json"
                reviews = {}
                if os.path.exists(review_path):
                    with open(review_path, 'r', encoding='utf-8') as f:
                        reviews = json.load(f)

                reviews[case_id] = {
                    "status": status,
                    "reviewer_notes": reviewer_notes,
                    "corrected_fix_steps": corrected_fix_steps
                }

                with open(review_path, 'w', encoding='utf-8') as f:
                    json.dump(reviews, f, indent=4)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                print(f"[+] Human review saved successfully for Case {case_id} (Status: {status})")

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                print(f"[-] Error saving human review: {e}")
        else:
            self.send_response(404)
            self.end_headers()

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    pass

def start_server():
    server_address = ('', PORT)
    httpd = ThreadingHTTPServer(server_address, CustomHandler)
    print(f"[+] NetSage AI Web Server successfully started.")
    print(f"[+] Click here to open the dashboard: http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[-] Shutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    start_server()
