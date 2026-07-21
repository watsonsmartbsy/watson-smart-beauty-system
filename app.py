from flask import Flask, render_template, request, redirect, session
import os
import io
import re

from datetime import datetime
from werkzeug.utils import secure_filename

import psycopg2
from psycopg2.extras import RealDictCursor

from modules.image_processing import analyze_skin
from modules.rule_engine import skin_condition
from modules.recommendation import get_recommendation

from reportlab.pdfgen import canvas
from flask import send_file

app = Flask(__name__)
app.secret_key = "secret123"

# -------------------------
# UPLOAD CONFIG
# -------------------------
UPLOAD_FOLDER = "static/uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

# -------------------------
# DATABASE CONNECTION
# -------------------------
def get_db():
    conn = psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=RealDictCursor
    )
    return conn


# -------------------------
# HOME PAGE
# -------------------------
@app.route('/')
def home():
    return render_template('login.html')


# -------------------------
# REGISTER PAGE
# -------------------------
@app.route('/register')
def register_page():
    return render_template('register.html')


# -------------------------
# CUSTOMER REGISTER
# -------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

        if not re.match(email_pattern, email):
            return render_template(
                "register.html",
                error="Invalid email format"
            )

        if password != confirm_password:
            return render_template(
                "register.html",
                error="Password does not match"
            )

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM users
            WHERE email=%s
        """, (email,))

        existing_user = cur.fetchone()

        if existing_user:
            cur.close()
            conn.close()

            return render_template(
                "register.html",
                error="Email already registered"
            )

        cur.execute("""
            INSERT INTO users
            (
                name,
                email,
                password,
                role
            )
            VALUES
            (%s,%s,%s,'user')
        """, (
            name,
            email,
            password
        ))

        conn.commit()

        cur.close()
        conn.close()

        return render_template(
            "register.html",
            success="Account created successfully. Please login."
        )

    return render_template("register.html")


# -------------------------
# LOGIN FUNCTION
# -------------------------
@app.route('/login', methods=['POST'])
def login():

    session.clear()

    email = request.form['email']
    password = request.form['password']

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM users
        WHERE email=%s
        AND password=%s
    """, (
        email,
        password
    ))

    user = cur.fetchone()

    cur.close()
    conn.close()

    if user:

        session['user_id'] = user['id']
        session['name'] = user['name']
        session['role'] = user['role']

        if user['role'] == 'admin':
            return redirect('/admin')

        elif user['role'] == 'worker':
            return redirect('/worker')

        else:
            return redirect('/dashboard')

    return render_template(
        "login.html",
        error="Incorrect email or password"
    )


# -------------------------
# USER DASHBOARD
# -------------------------
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM users
        WHERE id=%s
    """, (
        session['user_id'],
    ))

    user = cur.fetchone()

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM analysis_history
        WHERE user_id=%s
    """, (
        session['user_id'],
    ))

    total_analysis = cur.fetchone()['total']

    cur.execute("""
        SELECT *
        FROM analysis_history
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT 1
    """, (
        session['user_id'],
    ))

    latest = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "dashboard.html",
        user=user,
        total_analysis=total_analysis,
        latest=latest
    )


# ==================================================
# CUSTOMER PROFILE
# ==================================================
@app.route('/profile')
def profile():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM users
        WHERE id=%s
    """, (
        session['user_id'],
    ))

    user = cur.fetchone()

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM analysis_history
        WHERE user_id=%s
    """, (
        session['user_id'],
    ))

    total_analysis = cur.fetchone()['total']

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM feedback
        WHERE user_id=%s
    """, (
        session['user_id'],
    ))

    total_feedback = cur.fetchone()['total']

    cur.close()
    conn.close()

    return render_template(
        "profile.html",
        user=user,
        total_analysis=total_analysis,
        total_feedback=total_feedback
    )


# ==================================================
# UPDATE CUSTOMER PROFILE
# ==================================================
@app.route('/update_profile', methods=['POST'])
def update_profile():

    if 'user_id' not in session:
        return redirect('/')

    name = request.form['name']
    email = request.form['email']

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET
            name=%s,
            email=%s
        WHERE id=%s
    """, (
        name,
        email,
        session['user_id']
    ))

    conn.commit()

    cur.close()
    conn.close()

    session['name'] = name

    return redirect('/profile')


# ==================================================
# CHANGE PASSWORD
# ==================================================
@app.route('/change_password', methods=['POST'])
def change_password():

    if 'user_id' not in session:
        return redirect('/')

    old_password = request.form['old_password']
    new_password = request.form['new_password']

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM users
        WHERE id=%s
    """, (
        session['user_id'],
    ))

    user = cur.fetchone()

    if user['password'] != old_password:

        cur.close()
        conn.close()

        return render_template(
            "profile.html",
            user=user,
            error="Old password incorrect"
        )

    cur.execute("""
        UPDATE users
        SET password=%s
        WHERE id=%s
    """, (
        new_password,
        session['user_id']
    ))

    conn.commit()

    cur.close()
    conn.close()

    return render_template(
        "profile.html",
        user=user,
        success="Password updated successfully"
    )

# -------------------------
# WORKER DASHBOARD
# -------------------------
@app.route('/worker')
def worker():

    if session.get('role') != 'worker':
        return redirect('/')

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    # Total Analysis
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM analysis_history
    """)
    total_analysis = cur.fetchone()['total']

    # Total Products
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM products
    """)
    total_products = cur.fetchone()

    # Total Rules
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM rules
    """)
    total_rules = cur.fetchone()

    # Latest Analysis
    cur.execute("""
        SELECT *
        FROM analysis_history
        ORDER BY id DESC
        LIMIT 1
    """)
    latest_analysis = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        'worker.html',
        total_analysis=total_analysis,
        total_products=total_products['total'],
        total_rules=total_rules['total'],
        latest_analysis=latest_analysis
    )


# ==================================================
# ADMIN DASHBOARD
# ==================================================
@app.route('/admin')
def admin_dashboard():

    if session.get('role') != 'admin':
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    # =============================
    # TOTAL USERS
    # =============================
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM users
        WHERE role='user'
        OR role='customer'
    """)
    total_users = cur.fetchone()['total']

    # =============================
    # TOTAL WORKERS
    # =============================
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM users
        WHERE role='worker'
    """)
    total_workers = cur.fetchone()['total']

    # =============================
    # TOTAL PRODUCTS
    # =============================
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM products
    """)
    total_products = cur.fetchone()['total']

    # =============================
    # TOTAL ANALYSIS
    # =============================
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM analysis_history
    """)
    total_analysis = cur.fetchone()['total']

    # =============================
    # PENDING FEEDBACK
    # =============================
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM feedback
        WHERE status='Pending'
    """)
    pending_feedback = cur.fetchone()['total']

    # =============================
    # RESOLVED FEEDBACK
    # =============================
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM feedback
        WHERE status='Resolved'
    """)
    resolved_feedback = cur.fetchone()['total']

    # =============================
    # SKIN CONDITION STATISTICS
    # =============================
    cur.execute("""
        SELECT
            condition,
            COUNT(*) AS total
        FROM analysis_history
        GROUP BY condition
    """)
    skin_stats = cur.fetchall()

    # =============================
    # TOP PRODUCT
    # =============================
    cur.execute("""
        SELECT
            product,
            COUNT(*) AS total
        FROM analysis_history
        GROUP BY product
        ORDER BY total DESC
        LIMIT 1
    """)
    top_product = cur.fetchone()

    # =============================
    # CHART DATA
    # =============================
    chart_labels = []
    chart_values = []

    for stat in skin_stats:
        chart_labels.append(stat['condition'])
        chart_values.append(stat['total'])

    cur.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_workers=total_workers,
        total_products=total_products,
        total_analysis=total_analysis,
        skin_stats=skin_stats,
        pending_feedback=pending_feedback,
        resolved_feedback=resolved_feedback,
        top_product=top_product,
        chart_labels=list(chart_labels),
        chart_values=list(chart_values)
    )

# ==================================================
# ADMIN VIEW USERS
# ==================================================
@app.route('/admin/users')
def manage_users():

    if session.get('role') != 'admin':
        return redirect('/')

    search = request.args.get('search', '')

    print("SEARCH VALUE:", search)

    conn = get_db()
    cur = conn.cursor()

    query = """
        SELECT *
        FROM users
        WHERE role != 'admin'
    """

    params = []

    if search:

        query += """
            AND
            (
                name ILIKE %s
                OR email ILIKE %s
            )
        """

        params.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    query += """
        ORDER BY id DESC
    """

    cur.execute(query, tuple(params))

    users = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "manage_users.html",
        users=users,
        search=search
    )


# ==================================================
# ADD WORKER PAGE
# ==================================================
@app.route('/admin/add_worker')
def add_worker_page():

    if session.get('role') != 'admin':
        return redirect('/')

    return render_template(
        'add_worker.html'
    )


# ==================================================
# CREATE WORKER ACCOUNT
# ==================================================
@app.route('/admin/create_worker', methods=['POST'])
def create_worker():

    if session.get('role') != 'admin':
        return redirect('/')

    name = request.form['name']
    email = request.form['email']
    password = request.form['password']

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users
        (
            name,
            email,
            password,
            role
        )
        VALUES
        (
            %s, %s, %s, 'worker'
        )
    """,
    (
        name,
        email,
        password
    ))

    conn.commit()

    cur.close()
    conn.close()

    return redirect('/admin')


# ==================================================
# DELETE USER / WORKER
# ==================================================
@app.route('/admin/delete_user/<int:id>')
def delete_user(id):

    if session.get('role') != 'admin':
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM users
        WHERE id=%s
        AND role!='admin'
    """,
    (
        id,
    ))

    conn.commit()

    cur.close()
    conn.close()

    return redirect('/admin/users')

# -------------------------
# UPLOAD PAGE
# -------------------------
@app.route('/upload')
def upload_page():

    if 'user_id' not in session:
        return redirect('/')

    return render_template('upload.html')


# -------------------------
# IMAGE UPLOAD + ANALYSIS
# -------------------------
@app.route('/upload', methods=['GET', 'POST'])
def upload_image():

    if 'user_id' not in session:
        return redirect('/')

    # SHOW UPLOAD PAGE
    if request.method == "GET":
        return render_template("upload.html")

    # PROCESS IMAGE
    if 'image' not in request.files:
        return "No file uploaded"

    file = request.files['image']

    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

    if file.filename == '':
        return "No selected file"

    filename = secure_filename(file.filename)

    filepath = os.path.join(
        app.config['UPLOAD_FOLDER'],
        filename
    )

    # SAVE IMAGE
    file.save(filepath)

    # ANALYZE IMAGE
    result = analyze_skin(filepath)

    # FACE NOT DETECTED
    if 'error' in result:
        return result['error']

    conn = get_db()
    cur = conn.cursor()

    # RULE ENGINE
    rule_result = skin_condition(
        result['brightness'],
        result['redness'],
        result['texture'],
        conn
    )

    condition = rule_result['condition']
    advice = rule_result['advice']
    severity = rule_result['severity']

    # =========================
    # GET SKINCARE ROUTINE
    # =========================

    cur.execute("""
        SELECT *
        FROM products
        WHERE skin_type=%s
        AND category=%s
        LIMIT 1
    """, (
        condition,
        "Cleanser"
    ))
    cleanser = cur.fetchone()

    cur.execute("""
        SELECT *
        FROM products
        WHERE skin_type=%s
        AND category=%s
        LIMIT 1
    """, (
        condition,
        "Toner"
    ))
    toner = cur.fetchone()

    cur.execute("""
        SELECT *
        FROM products
        WHERE skin_type=%s
        AND category=%s
        LIMIT 1
    """, (
        condition,
        "Serum"
    ))
    serum = cur.fetchone()

    cur.execute("""
        SELECT *
        FROM products
        WHERE skin_type=%s
        AND category=%s
        LIMIT 1
    """, (
        condition,
        "Moisturizer"
    ))
    moisturizer = cur.fetchone()

    # PRODUCT RECOMMENDATION
    print(get_recommendation)
    print(get_recommendation.__code__.co_argcount)

    recommendation = get_recommendation(
        condition,
        severity,
        conn
    )

    # DEFAULT VALUES
    product_name = "No Product Found"
    product_category = "-"
    product_price = "-"
    product_image = ""

    # IF PRODUCT EXISTS
    if recommendation:
        product_name = recommendation['product_name']
        product_category = recommendation['category']
        product_price = recommendation['price']
        product_image = recommendation['image']

    # SAVE HISTORY
    cur.execute("""
        INSERT INTO analysis_history
        (
            user_id,
            image_path,
            brightness,
            redness,
            texture,
            condition,
            product,
            advice,
            severity
        )
        VALUES
        (
            %s,%s,%s,%s,%s,%s,%s,%s,%s
        )
    """,
    (
        session['user_id'],
        filepath,
        result['brightness'],
        result['redness'],
        result['texture'],
        condition,
        product_name,
        advice,
        severity
    ))

    conn.commit()

    cur.close()
    conn.close()

    # =========================
    # SKINCARE ROUTINE PRODUCTS
    # =========================

    conn = get_db()
    cur = conn.cursor()

    # Morning Routine

    cur.execute("""
        SELECT *
        FROM products
        WHERE skin_type=%s
        AND category='Cleanser'
        LIMIT 1
    """, (condition,))
    cleanser = cur.fetchone()

    cur.execute("""
        SELECT *
        FROM products
        WHERE skin_type=%s
        AND category='Toner'
        LIMIT 1
    """, (condition,))
    toner = cur.fetchone()

    cur.execute("""
        SELECT *
        FROM products
        WHERE skin_type=%s
        AND category='Moisturizer'
        LIMIT 1
    """, (condition,))
    moisturizer = cur.fetchone()

    cur.execute("""
        SELECT *
        FROM products
        WHERE skin_type=%s
        AND category='Serum'
        LIMIT 1
    """, (condition,))
    serum = cur.fetchone()

    cur.execute("""
        SELECT *
        FROM products
        WHERE skin_type=%s
        AND category='Sunscreen'
        LIMIT 1
    """, (condition,))
    sunscreen = cur.fetchone()

    cur.close()
    conn.close()

    brightness_percent = round(result['brightness'] / 255 * 100, 1)
    redness_percent = round(result['redness'] / 255 * 100, 1)
    texture_percent = round(result['texture'] / 255 * 100, 1)

    print("Filename =", filename)
    print("Passing image_path =", filename)

    return render_template(
        "result.html",

        brightness=result['brightness'],
        redness=result['redness'],
        texture=result['texture'],

        brightness_percent=brightness_percent,
        redness_percent=redness_percent,
        texture_percent=texture_percent,

        condition=condition,
        advice=advice,
        severity=severity,

        cleanser=cleanser,
        toner=toner,
        serum=serum,
        moisturizer=moisturizer,
        sunscreen=sunscreen,

        image_path=filename
    )


# -------------------------
# ANALYSIS HISTORY
# -------------------------
@app.route('/history')
def history():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM analysis_history
        WHERE user_id=%s
        ORDER BY id DESC
    """, (
        session['user_id'],
    ))

    history = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "history.html",
        history=history
    )


# -------------------------
# DELETE ANALYSIS HISTORY
# -------------------------
@app.route('/history/delete/<int:id>')
def delete_history(id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM analysis_history
        WHERE id=%s
        AND user_id=%s
    """, (
        id,
        session['user_id']
    ))

    conn.commit()

    cur.close()
    conn.close()

    return redirect('/history')


# -------------------------
# VIEW ANALYSIS DETAIL
# -------------------------
@app.route('/history/view/<int:id>')
def view_history(id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM analysis_history
        WHERE id=%s
        AND user_id=%s
    """, (
        id,
        session['user_id']
    ))

    record = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "history_detail.html",
        record=record
    )


# -------------------------
# WORKER REVIEW HISTORY
# -------------------------
@app.route('/worker/history')
def worker_history():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM analysis_history
        ORDER BY id DESC
    """)

    history = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'worker_history.html',
        history=history
    )

# ==================================================
# WORKER VIEW CUSTOMER ANALYSIS
# ==================================================

@app.route('/worker/analysis')
def worker_analysis():

    if session.get('role') != 'worker':
        return redirect('/')

    search = request.args.get(
        'search',
        ''
    )

    condition = request.args.get(
        'condition',
        ''
    )

    conn = get_db()
    cur = conn.cursor()

    query = """
        SELECT
            analysis_history.*,
            users.name,
            users.email

        FROM analysis_history

        JOIN users
        ON analysis_history.user_id = users.id

        WHERE 1=1
    """

    params = []

    if search:

        query += """
            AND users.name ILIKE %s
        """

        params.append(
            f"%{search}%"
        )

    if condition:

        query += """
            AND analysis_history.condition = %s
        """

        params.append(condition)

    query += """
        ORDER BY analysis_history.id DESC
    """

    cur.execute(
        query,
        tuple(params)
    )

    records = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "worker_analysis.html",
        records=records,
        search=search,
        condition=condition
    )


# -------------------------
# ADD PRODUCT PAGE
# -------------------------
@app.route('/worker/add_product')
def add_product_page():

    return render_template(
        'add_product.html'
    )


# -------------------------
# SAVE PRODUCT
# -------------------------
@app.route('/worker/add_product', methods=['POST'])
def add_product():

    product_name = request.form['product_name']
    category = request.form['category']
    skin_type = request.form['skin_type']
    price = request.form['price']

    image = request.files['image']

    print(request.form)

    description = request.form.get('description')
    benefits = request.form.get('benefits')
    ingredients = request.form.get('ingredients')
    how_to_use = request.form.get('how_to_use')

    image_filename = secure_filename(
        image.filename
    )

    image.save(
        os.path.join(
            app.config['UPLOAD_FOLDER'],
            image_filename
        )
    )

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO products
        (
            product_name,
            category,
            skin_type,
            description,
            benefits,
            ingredients,
            how_to_use,
            price,
            image
        )
        VALUES
        (
            %s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            product_name,
            category,
            skin_type,
            description,
            benefits,
            ingredients,
            how_to_use,
            price,
            image_filename
        )
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect('/worker/products')

# -------------------------
# PRODUCT LIST
# -------------------------
@app.route('/worker/products')
def worker_products():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM products
    """)

    products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'worker_products.html',
        products=products
    )


# -------------------------
# DELETE PRODUCT
# -------------------------
@app.route('/worker/delete_product/<int:id>')
def delete_product(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM products
        WHERE id=%s
    """, (
        id,
    ))

    conn.commit()

    cur.close()
    conn.close()

    return redirect('/worker/products')


# -------------------------
# ADD RULE PAGE
# -------------------------
@app.route('/worker/add_rule')
def add_rule_page():

    return render_template(
        'add_rule.html'
    )


# -------------------------
# SAVE RULE
# -------------------------
@app.route('/worker/add_rule', methods=['POST'])
def add_rule():

    condition_name = request.form['condition_name']
    min_brightness = request.form['min_brightness']
    max_brightness = request.form['max_brightness']
    min_redness = request.form['min_redness']
    max_redness = request.form['max_redness']
    advice = request.form['advice']

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO rules
        (
            condition_name,
            min_brightness,
            max_brightness,
            min_redness,
            max_redness,
            advice
        )
        VALUES
        (
            %s,%s,%s,%s,%s,%s
        )
    """,
    (
        condition_name,
        min_brightness,
        max_brightness,
        min_redness,
        max_redness,
        advice
    ))

    conn.commit()

    cur.close()
    conn.close()

    return redirect('/worker/rules')


# -------------------------
# VIEW RULES
# -------------------------
@app.route('/worker/rules')
def worker_rules():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM rules
    """)

    rules = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'worker_rules.html',
        rules=rules
    )


# -------------------------
# EDIT RULE PAGE
# -------------------------
@app.route('/worker/edit_rule/<int:id>')
def edit_rule_page(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM rules
        WHERE id=%s
    """, (
        id,
    ))

    rule = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        'edit_rule.html',
        rule=rule
    )


# -------------------------
# UPDATE RULE
# -------------------------
@app.route('/worker/update_rule/<int:id>', methods=['POST'])
def update_rule(id):

    condition_name = request.form['condition_name']
    min_brightness = request.form['min_brightness']
    max_brightness = request.form['max_brightness']
    min_redness = request.form['min_redness']
    max_redness = request.form['max_redness']
    advice = request.form['advice']

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE rules
        SET
            condition_name=%s,
            min_brightness=%s,
            max_brightness=%s,
            min_redness=%s,
            max_redness=%s,
            advice=%s
        WHERE id=%s
    """,
    (
        condition_name,
        min_brightness,
        max_brightness,
        min_redness,
        max_redness,
        advice,
        id
    ))

    conn.commit()

    cur.close()
    conn.close()

    return redirect('/worker/rules')


# -------------------------
# DELETE RULE
# -------------------------
@app.route('/worker/delete_rule/<int:id>')
def delete_rule(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM rules
        WHERE id=%s
    """, (
        id,
    ))

    conn.commit()

    cur.close()
    conn.close()

    return redirect('/worker/rules')


# -------------------------
# WORKER STATISTICS
# -------------------------
@app.route('/worker/statistics')
def worker_statistics():

    print("Statistics page opened")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM analysis_history
    """)

    total = cur.fetchone()['total']

    print("Total analyses:", total)

    cur.execute("""
        SELECT
            condition,
            COUNT(*) AS total
        FROM analysis_history
        GROUP BY condition
    """)

    conditions = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'statistics.html',
        total=total,
        conditions=conditions,
        chart_labels=[row['condition'] for row in conditions],
        chart_values=[row['total'] for row in conditions]
    )

@app.route('/admin/analysis_history')
def admin_analysis_history():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            analysis_history.*,
            users.name
        FROM analysis_history
        JOIN users
            ON analysis_history.user_id = users.id
        ORDER BY analysis_history.id DESC
    """)

    analyses = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "admin_analysis_history.html",
        analyses=analyses
    )


@app.route('/admin/view_history/<int:id>')
def admin_view_history(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            analysis_history.*,
            users.name,
            users.email
        FROM analysis_history
        JOIN users
            ON analysis_history.user_id = users.id
        WHERE analysis_history.id=%s
    """,
    (
        id,
    ))

    analysis = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "admin_view_history.html",
        analysis=analysis
    )


# -------------------------
# LOGOUT
# -------------------------
@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')


# ==================================================
# DOWNLOAD BEAUTY REPORT PDF
# ==================================================
@app.route('/download_report')
def download_report():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    # USER INFO
    cur.execute("""
        SELECT *
        FROM users
        WHERE id=%s
    """,
    (
        session['user_id'],
    ))

    user = cur.fetchone()

    # LATEST ANALYSIS
    cur.execute("""
        SELECT *
        FROM analysis_history
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT 1
    """,
    (
        session['user_id'],
    ))

    analysis = cur.fetchone()

    if not analysis:

        cur.close()
        conn.close()

        return "No analysis found"

    # PRODUCT RECOMMENDATION
    cur.execute("""
        SELECT *
        FROM products
        WHERE skin_type=%s

        ORDER BY

        CASE category
            WHEN 'Cleanser' THEN 1
            WHEN 'Toner' THEN 2
            WHEN 'Serum' THEN 3
            WHEN 'Moisturizer' THEN 4
            WHEN 'Sunscreen' THEN 5
        END
    """,
    (
        analysis['condition'],
    ))

    products = cur.fetchall()

    cur.close()
    conn.close()

    # CREATE PDF

    buffer = io.BytesIO()

    pdf = canvas.Canvas(buffer)

   # ==========================
    # HEADER
    # ==========================


    logo_path = os.path.join(
        "static",
        "image",
        "watson-logo.png"
    )


    if os.path.exists(logo_path):

        pdf.drawImage(
            logo_path,
            50,
            765,
            width=80,
            height=50,
            preserveAspectRatio=True
        )



    pdf.setFont("Helvetica-Bold",22)


    pdf.drawString(
        150,
        800,
        "Watson Smart Beauty"
    )


    pdf.setFont("Helvetica-Bold",18)


    pdf.drawString(
        150,
        775,
        "Advisory Report"
    )


    pdf.setFont("Helvetica",11)


    pdf.drawString(
        150,
        755,
        "Personalized Skin Analysis Report"
    )


    pdf.line(
        50,
        735,
        550,
        735
    )



    # DATE

    pdf.setFont(
        "Helvetica",
        10
    )


    pdf.drawString(
        50,
        715,
        "Generated Date: "
        + datetime.now().strftime("%d/%m/%Y")
    )




    # ==========================
    # CUSTOMER INFO
    # ==========================


    pdf.setFont(
        "Helvetica-Bold",
        15
    )


    pdf.drawString(
        50,
        670,
        "Customer Information"
    )



    pdf.setFont(
        "Helvetica",
        12
    )


    pdf.drawString(
        70,
        645,
        "Name: "
        + user['name']
    )


    pdf.drawString(
        70,
        625,
        "Email: "
        + user['email']
    )




    # ==========================
    # ANALYSIS RESULT
    # ==========================


    pdf.setFont(
        "Helvetica-Bold",
        15
    )


    pdf.drawString(
        50,
        575,
        "Skin Analysis Result"
    )


    pdf.setFont(
        "Helvetica",
        12
    )


    pdf.drawString(
        70,
        550,
        "Detected Condition: "
        + analysis['condition']
    )


    pdf.drawString(
        70,
        530,
        "Severity Level: "
        + analysis['severity']
    )


    pdf.drawString(
        70,
        510,
        "Brightness Score: "
        + str(analysis['brightness'])
    )


    pdf.drawString(
        70,
        490,
        "Redness Score: "
        + str(analysis['redness'])
    )


    pdf.drawString(
        70,
        470,
        "Texture Score: "
        + str(analysis['texture'])
    )


    # ==========================
    # SKINCARE ROUTINE
    # ==========================

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, 430, "Recommended Skincare Routine")

    # MORNING ROUTINE
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(70, 400, "Morning Routine")

    y = 375

    pdf.setFont("Helvetica", 11)

    if products:

        for p in products:

            pdf.drawString(
                90,
                y,
                p['category'] + " : " + p['product_name']
            )

            y -= 18

    else:

        pdf.drawString(
            90,
            y,
            "No product recommendation available"
        )

    # NIGHT ROUTINE

    y -= 30

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(70, y, "Night Routine")

    y -= 25

    pdf.setFont("Helvetica", 11)

    for p in products:

        if p['category'] != "Sunscreen":

            pdf.drawString(
                90,
                y,
                p['category'] + " : " + p['product_name']
            )

            y -= 18

    # ==========================
    # BEAUTY ADVICE
    # ==========================

    y -= 30

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, y, "Beauty Advice")

    y -= 25

    pdf.setFont("Helvetica", 11)

    pdf.drawString(
        70,
        y,
        analysis['advice']
    )

    # FOOTER

    pdf.line(50, 80, 550, 80)

    pdf.setFont("Helvetica", 10)

    pdf.drawString(
        150,
        60,
        "Generated by Watson Smart Beauty Advisory System"
    )

    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="Watson_Beauty_Report.pdf",
        mimetype="application/pdf"
    )


# ==================================================
# CUSTOMER FEEDBACK
# ==================================================

@app.route('/feedback')
def feedback():

    if 'user_id' not in session:
        return redirect('/')

    return render_template('feedback.html')


@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():

    if 'user_id' not in session:
        return redirect('/')

    subject = request.form['subject']
    category = request.form['category']
    message = request.form['message']

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO feedback
        (
            user_id,
            subject,
            category,
            message
        )
        VALUES
        (
            %s,%s,%s,%s
        )
    """,
    (
        session['user_id'],
        subject,
        category,
        message
    ))

    conn.commit()

    cur.close()
    conn.close()

    return "Feedback submitted successfully!"


# ==================================================
# WORKER FEEDBACK
# ==================================================

@app.route('/worker/feedback')
def worker_feedback():

    if session.get('role') != 'worker':
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            feedback.*,
            users.name
        FROM feedback
        LEFT JOIN users
        ON feedback.user_id = users.id
        ORDER BY feedback.created_at DESC
    """)

    feedbacks = cur.fetchall()

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM feedback
        WHERE status='Pending'
    """)
    pending = cur.fetchone()['total']

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM feedback
        WHERE status='Resolved'
    """)
    resolved = cur.fetchone()['total']

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM feedback
    """)
    total = cur.fetchone()['total']

    cur.close()
    conn.close()

    return render_template(
        "worker_feedback.html",
        feedbacks=feedbacks,
        pending=pending,
        resolved=resolved,
        total=total
    )


@app.route('/worker/view_feedback/<int:id>')
def view_feedback(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            feedback.id,
            feedback.user_id,
            feedback.subject,
            feedback.category,
            feedback.message,
            feedback.status,
            feedback.created_at,
            users.name AS customer_name,
            users.email AS customer_email
        FROM feedback
        JOIN users
        ON feedback.user_id = users.id
        WHERE feedback.id=%s
    """,
    (
        id,
    ))

    feedback = cur.fetchone()

    cur.close()
    conn.close()

    if feedback is None:
        return "Feedback not found"

    return render_template(
        "view_feedback.html",
        feedback=feedback
    )


@app.route('/worker/resolve_feedback/<int:id>')
def resolve_feedback(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE feedback
        SET status='Resolved'
        WHERE id=%s
    """,
    (
        id,
    ))

    conn.commit()

    cur.close()
    conn.close()

    return redirect('/worker/feedback')


# -------------------------
# RUN APP
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)
