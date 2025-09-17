from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>🎉 Flask is LIVE!</h1><p>Your Python backend is running on port 3000.</p>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
