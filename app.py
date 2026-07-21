from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename


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


# -------------------------
# DATABASE CONNECTION
# -------------------------
def get_db():

    conn = sqlite3.connect("database.db")

    conn.row_factory = sqlite3.Row

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
# REGISTER FUNCTION
# -------------------------
@app.route('/register', methods=['POST'])
def register():

    name = request.form['name']

    email = request.form['email']

    password = request.form['password']

    role = request.form['role'].strip().lower()

    conn = get_db()

    existing_user = conn.execute(
        '''
        SELECT * FROM users
        WHERE email = ?
        ''',
        (email,)
    ).fetchone()

    if existing_user:

        conn.close()

        return "Email already exists"

    conn.execute(
        '''
        INSERT INTO users
        (name, email, password, role)
        VALUES (?, ?, ?, ?)
        ''',
        (name, email, password, role)
    )

    conn.commit()

    conn.close()

    return redirect('/')


# -------------------------
# LOGIN FUNCTION
# -------------------------
@app.route('/login', methods=['POST'])
def login():

    email = request.form['email']

    password = request.form['password']

    conn = get_db()

    user = conn.execute(
        '''
        SELECT * FROM users
        WHERE email = ? AND password = ?
        ''',
        (email, password)
    ).fetchone()

    conn.close()

    if user:

        session['user_id'] = user['id']
        session['role'] = user['role']

        if user['role'] == 'admin':

            return redirect('/admin')

        elif user['role'] == 'worker':

            return redirect('/worker')

        else:

            return redirect('/dashboard')

    return redirect('/')

# -------------------------
# USER DASHBOARD
# -------------------------
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:

        return redirect('/')

    return render_template('dashboard.html')


# -------------------------
# WORKER DASHBOARD
# -------------------------
@app.route('/worker')
def worker():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db()

    total_analysis = conn.execute(
        '''
        SELECT COUNT(*) AS total
        FROM analysis_history
        '''
    ).fetchone()

    total_products = conn.execute(
        '''
        SELECT COUNT(*) AS total
        FROM products
        '''
    ).fetchone()

    total_rules = conn.execute(
        '''
        SELECT COUNT(*) AS total
        FROM rules
        '''
    ).fetchone()

    latest_analysis = conn.execute(
        '''
        SELECT *
        FROM analysis_history
        ORDER BY id DESC
        LIMIT 1
        '''
    ).fetchone()

    conn.close()

    return render_template(
        'worker.html',
        total_analysis=total_analysis['total'],
        total_products=total_products['total'],
        total_rules=total_rules['total'],
        latest_analysis=latest_analysis
    )


# -------------------------
# ADMIN DASHBOARD
# -------------------------
@app.route('/admin')
def admin_dashboard():

    if session.get('role') != 'admin':
        return redirect('/')

    return render_template('admin_dashboard.html')

@app.route('/admin/add_worker')
def add_worker_page():

    if session.get('role') != 'admin':
        return redirect('/')

    return render_template('add_worker.html')

@app.route('/admin/create_worker', methods=['POST'])
def create_worker():

    if session.get('role') != 'admin':
        return redirect('/')

    name = request.form['name']
    email = request.form['email']
    password = request.form['password']

    conn = get_db()

    conn.execute(
        '''
        INSERT INTO users
        (name,email,password,role)

        VALUES
        (?,?,?,'worker')
        ''',
        (name,email,password)
    )

    conn.commit()
    conn.close()

    return redirect('/admin')

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
@app.route('/upload', methods=['POST'])
def upload_image():

    if 'user_id' not in session:

        return redirect('/')

    if 'image' not in request.files:

        return "No file uploaded"

    file = request.files['image']

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

    # RULE ENGINE
    rule_result = skin_condition(
        result['brightness'],
        result['redness'],
        conn
    )

    condition = rule_result['condition']

    advice = rule_result['advice']

    severity = rule_result['severity']

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
    conn.execute(
        '''
        INSERT INTO analysis_history
        (
            user_id,
            image_path,
            brightness,
            redness,
            condition,
            product,
            advice,
            severity
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            session['user_id'],
            filepath,
            result['brightness'],
            result['redness'],
            condition,
            product_name,
            advice,
            severity
        )
    )

    conn.commit()

    conn.close()

    # SHOW RESULT
    return render_template(
        'result.html',
        brightness=result['brightness'],
        redness=result['redness'],
        condition=condition,
        severity=severity,
        product=product_name,
        category=product_category,
        price=product_price,
        image=product_image,
        advice=advice
    )


# -------------------------
# USER HISTORY
# -------------------------
@app.route('/history')
def history():

    if 'user_id' not in session:

        return redirect('/')

    conn = get_db()

    history = conn.execute(
        '''
        SELECT * FROM analysis_history
        WHERE user_id = ?
        ORDER BY id DESC
        ''',
        (session['user_id'],)
    ).fetchall()

    conn.close()

    return render_template(
        'history.html',
        history=history
    )


# -------------------------
# WORKER REVIEW HISTORY
# -------------------------
@app.route('/worker/history')
def worker_history():

    if 'user_id' not in session:

        return redirect('/')

    conn = get_db()

    history = conn.execute(
        '''
        SELECT * FROM analysis_history
        ORDER BY id DESC
        '''
    ).fetchall()

    conn.close()

    return render_template(
        'worker_history.html',
        history=history
    )


# -------------------------
# ADD PRODUCT PAGE
# -------------------------
@app.route('/worker/add_product')
def add_product_page():

    return render_template('add_product.html')


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

    conn.execute(
        '''
        INSERT INTO products
        (
            product_name,
            category,
            skin_type,
            price,
            image
        )
        VALUES (?, ?, ?, ?, ?)
        ''',
        (
            product_name,
            category,
            skin_type,
            price,
            image_filename
        )
    )

    conn.commit()

    conn.close()

    return redirect('/worker/products')


# -------------------------
# PRODUCT LIST
# -------------------------
@app.route('/worker/products')
def worker_products():

    conn = get_db()

    products = conn.execute(
        '''
        SELECT * FROM products
        '''
    ).fetchall()

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

    conn.execute(
        '''
        DELETE FROM products
        WHERE id = ?
        ''',
        (id,)
    )

    conn.commit()

    conn.close()

    return redirect('/worker/products')


# -------------------------
# ADD RULE PAGE
# -------------------------
@app.route('/worker/add_rule')
def add_rule_page():

    return render_template('add_rule.html')


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

    conn.execute(
        '''
        INSERT INTO rules
        (
            condition_name,
            min_brightness,
            max_brightness,
            min_redness,
            max_redness,
            advice
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (
            condition_name,
            min_brightness,
            max_brightness,
            min_redness,
            max_redness,
            advice
        )
    )

    conn.commit()

    conn.close()

    return redirect('/worker/rules')


# -------------------------
# VIEW RULES
# -------------------------
@app.route('/worker/rules')
def worker_rules():

    conn = get_db()

    rules = conn.execute(
        '''
        SELECT * FROM rules
        '''
    ).fetchall()

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

    rule = conn.execute(
        '''
        SELECT * FROM rules
        WHERE id = ?
        ''',
        (id,)
    ).fetchone()

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

    conn.execute(
        '''
        UPDATE rules
        SET
            condition_name = ?,
            min_brightness = ?,
            max_brightness = ?,
            min_redness = ?,
            max_redness = ?,
            advice = ?
        WHERE id = ?
        ''',
        (
            condition_name,
            min_brightness,
            max_brightness,
            min_redness,
            max_redness,
            advice,
            id
        )
    )

    conn.commit()

    conn.close()

    return redirect('/worker/rules')


# -------------------------
# DELETE RULE
# -------------------------
@app.route('/worker/delete_rule/<int:id>')
def delete_rule(id):

    conn = get_db()

    conn.execute(
        '''
        DELETE FROM rules
        WHERE id = ?
        ''',
        (id,)
    )

    conn.commit()

    conn.close()

    return redirect('/worker/rules')


@app.route('/worker/statistics')
def worker_statistics():

    print("Statistics page opened")

    conn = get_db()

    total = conn.execute(
        '''
        SELECT COUNT(*) AS total
        FROM analysis_history
        '''
    ).fetchone()

    print("Total analyses:", total['total'])

    conditions = conn.execute(
        '''
        SELECT condition,
               COUNT(*) AS total
        FROM analysis_history
        GROUP BY condition
        '''
    ).fetchall()

    conn.close()

    return render_template(
    'statistics.html',
    total=total,
    conditions=conditions,
    chart_labels=[row['condition'] for row in conditions],
    chart_values=[row['total'] for row in conditions]
)
# -------------------------
# LOGOUT
# -------------------------
@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')

@app.route('/download_report')
def download_report():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db()

    report = conn.execute(
        '''
        SELECT *
        FROM analysis_history
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        ''',
        (session['user_id'],)
    ).fetchone()

    conn.close()

    pdf_file = os.path.join(
        os.getcwd(),
        "analysis_report.pdf"
    )


    from datetime import datetime

    c = canvas.Canvas(pdf_file)

    try:

        c.drawImage(
            report['image_path'],
            340,
            590,
            width=150,
            height=110
        )

    except:
        pass

    # HEADER
    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, 800, "Watson Beauty Advisory System")

    c.setFont("Helvetica", 10)
    c.drawString(
        40,
        780,
        f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    c.line(40, 770, 550, 770)

    # ANALYSIS SUMMARY
    c.rect(40, 560, 500, 180)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 715, "Skin Analysis Summary")

    c.setFont("Helvetica", 12)

    c.drawString(60, 680, f"Brightness : {report['brightness']}")
    c.drawString(60, 655, f"Redness : {report['redness']}")
    c.drawString(60, 630, f"Condition : {report['condition']}")
    c.drawString(60, 605, f"Severity : {report['severity']}")
     # PRODUCT
    c.rect(40, 450, 500, 80)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 505, "Product Recommendation")

    c.setFont("Helvetica", 12)

    c.drawString(
        60,
        475,
        f"Recommended Product: {report['product']}"
    )

    # ADVICE
    c.rect(40, 300, 500, 120)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 390, "Skin Care Advice")

    c.setFont("Helvetica", 12)

    c.drawString(
        60,
        355,
        report['advice']
    )

    # FOOTER
    c.line(40, 100, 550, 100)

    c.setFont("Helvetica-Oblique", 10)

    c.drawString(
        40,
        80,
        "This report is generated automatically by the Watson Beauty Advisory System."
    )
    c.save()

    return send_file(
        pdf_file,
        as_attachment=True
    )
# -------------------------
# RUN APP
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)