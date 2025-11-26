from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
from werkzeug.security import check_password_hash, generate_password_hash
import os

app = Flask(__name__)

# Secret for session management
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-key")

# =====================================================================
# User Store (extendable, secure, supports env override for Jenkins)
# =====================================================================
DEFAULT_USERNAME = os.getenv("APP_USERNAME", "alice")
DEFAULT_PASSWORD = os.getenv("APP_PASSWORD", "password123")

USERS = {
    DEFAULT_USERNAME: generate_password_hash(DEFAULT_PASSWORD)
}

# =====================================================================
# Routes
# =====================================================================

@app.route("/", methods=["GET"])
def index():
    """Redirect root to either dashboard or login."""
    if session.get("user"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Render login page and validate user credentials."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        pw_hash = USERS.get(username)

        if pw_hash and check_password_hash(pw_hash, password):
            session["user"] = username
            flash("Login successful 🎉", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password", "error")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    """Secure dashboard — must be logged in."""
    user = session.get("user")

    if not user:
        return redirect(url_for("login"))

    # "Welcome" included so your PyTest passes correctly
    welcome_message = f"Welcome, {user}!"

    return render_template("dashboard.html", username=user, welcome_message=welcome_message)


@app.route("/logout")
def logout():
    """Clear the session and return to login."""
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# =====================================================================
# Main Entry
# =====================================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
