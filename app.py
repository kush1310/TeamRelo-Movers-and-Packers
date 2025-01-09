from flask import Flask, render_template, request, redirect, session, g, jsonify, flash, url_for
import sqlite3
import hashlib
import os
import uuid
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText    

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATABASE = 'movers_packers.db'

# Function to get database connection

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db


# Function to close database connection
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


# Database initialization
conn = sqlite3.connect('movers_packers.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS customer (
        id INTEGER PRIMARY KEY,
        full_name TEXT,
        email TEXT,
        mobile TEXT,
        address TEXT,
        password TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS booking (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        pickup_address TEXT,
        destination_address TEXT,
        remark TEXT,
        status TEXT,
        driver_id INTEGER,  -- Add a column for storing driver ID
        FOREIGN KEY (customer_id) REFERENCES customer(id),
        FOREIGN KEY (driver_id) REFERENCES driver(id)  -- Add foreign key constraint for driver ID
    )
''')


cursor.execute('''
    CREATE TABLE IF NOT EXISTS driver (
        id INTEGER PRIMARY KEY,
        name TEXT,
        email TEXT,
        mobile TEXT,
        availability INTEGER  -- 1 for available, 0 for not available
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY,
        full_name TEXT,
        email TEXT,
        contact_no TEXT,
        state TEXT,
        union_territory TEXT,
        message TEXT
    )
''')

default_admin_username = 'admin'
default_admin_password = 'password'  # Replace with your desired password
hashed_default_admin_password = hashlib.md5(default_admin_password.encode()).hexdigest()
default_driver_name = 'Kushagra Bhai'
default_driver_email = 'kddriver@teamrelo.ac.in'
default_driver_mobile = '9865432658'
default_driver_availability = 1

cursor.execute('SELECT COUNT(*) FROM driver WHERE name = ?', (default_driver_name,))
driver_count = cursor.fetchone()[0]

if driver_count == 0:
    cursor.execute('INSERT INTO driver (name, email, mobile, availability) VALUES (?, ?, ?, ?)',
               (default_driver_name, default_driver_email, default_driver_mobile, default_driver_availability))
    conn.commit()  # Don't forget to commit the transaction if using a database connection


# Check if default admin record already exists
cursor.execute('SELECT COUNT(*) FROM admin WHERE username = ?', (default_admin_username,))
admin_count = cursor.fetchone()[0]

if admin_count == 0:
    # Insert default admin with a static password
    cursor.execute('INSERT INTO admin (username, password) VALUES (?, ?)', (default_admin_username, hashed_default_admin_password))
    conn.commit()


# Other tables (about us, contact us, admin) would be defined similarly

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/contact/us' , methods = ['GET', 'POST'])
def contactus():
    if request.method == 'POST':
        full_name = request.form['fullname']
        email = request.form['email']
        contact_no = request.form['phone']
        state = request.form['state']
        union_territory = request.form['union_territory']
        message = request.form['message']

        cursor = get_db().cursor()
        cursor.execute('''INSERT INTO contacts (full_name, email, contact_no, state, union_territory, message)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (full_name, email, contact_no, state, union_territory, message))
        cursor.close()

        # Redirect to index.html after form submission
        return redirect(url_for('index'))

    return render_template('index.html')

# Admin Login
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.md5(request.form['password'].encode()).hexdigest()  # Hash password

        # Verify admin credentials
        cursor = get_db().cursor()
        cursor.execute('SELECT * FROM admin WHERE username = ? AND password = ?', (username, password))
        admin = cursor.fetchone()

        if admin:
            session['admin_logged_in'] = True
            return redirect('/admin/dashboard')
        else:
            return render_template('admin_login.html', error='Invalid credentials')
    return render_template('admin_login.html')

# Admin Dashboard
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_logged_in' not in session:
        return redirect('/admin/login')  # Redirect to admin login page if admin is not logged in

    # Fetch counts of pending, current, and completed bookings
    cursor = get_db().cursor()
    cursor.execute('SELECT COUNT(*) FROM booking WHERE status = ?', ('waiting',))
    pending_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM booking WHERE status = ?', ('approved  ',))
    current_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM booking WHERE status = ?', ('completed',))
    completed_count = cursor.fetchone()[0]

    return render_template('admin_dashboard.html', pending_count=pending_count, current_count=current_count, completed_count=completed_count)

# Customer Booking
@app.route('/booking', methods=['GET', 'POST'])
def customer_booking():
    if 'user_logged_in' not in session:
        return redirect('/login')  # Redirect to login page if user is not logged in

    if request.method == 'POST':
        # Get form data
        customer_id = session.get('customer_id')  # Retrieve customer ID from session
        pickup_address = request.form['pickup_address']
        destination_address = request.form['destination_address']
        remark = request.form['remark']
        status = 'driver_pending'  # Set status as 'driver_pending'

        # Assign booking directly to the static driver
        cursor = get_db().cursor()
        cursor.execute('SELECT id FROM driver LIMIT 1')
        driver_id = cursor.fetchone()[0]

        # Insert booking details into the database
        cursor.execute(
            'INSERT INTO booking (customer_id, pickup_address, destination_address, remark, status, driver_id) VALUES (?, ?, ?, ?, ?, ?)',
            (customer_id, pickup_address, destination_address, remark, status, driver_id))
        # Commit changes to the database
        get_db().commit()
        return redirect(url_for('user_dashboard'))

    return render_template('booking_form.html')

#user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Handle POST request (login form submission)
        customer_id = request.form['customer_id']
        password = request.form['password']

        # Retrieve user from the database based on customer ID
        cursor = get_db().cursor()
        cursor.execute('SELECT * FROM customer WHERE id = ?', (customer_id,))
        user = cursor.fetchone()

        if user:
            # Verify password
            hashed_password = hashlib.md5(password.encode()).hexdigest()
            if user[5] == hashed_password:  # Assuming password is stored in the sixth column
                # Set user data in session
                session['user_logged_in'] = True
                session['customer_id'] = customer_id
                return redirect(url_for('user_dashboard'))  # Redirect to user dashboard after successful login
            else:
                error = 'Incorrect password. Please try again.'
                return render_template('login.html', error=error)
        else:
            error = 'User does not exist. Please register.'
            return render_template('login.html', error=error)

    # Handle GET request (render login form)
    return render_template('login.html')

@app.route('/user/dashboard', methods=['GET', 'POST'])
def user_dashboard():
    if 'user_logged_in' not in session:
        return redirect('/login')

    if request.method == 'POST':
        customer_id = session.get('customer_id')
        if not customer_id:
            return "Customer ID is required", 400  # Return a 400 error if customer_id is not provided

        cursor = get_db().cursor()
        cursor.execute('SELECT * FROM booking WHERE customer_id = ?', (customer_id,))
        booking_data = cursor.fetchall()

        return render_template('user_dashboard.html', booking_data=booking_data, enumerate=enumerate)
    elif request.method == 'GET':
        customer_id = session.get('customer_id')
        if not customer_id:
            return redirect('/login') 

        cursor = get_db().cursor()
        cursor.execute('SELECT * FROM booking WHERE customer_id = ?', (customer_id,))
        booking_data = cursor.fetchall()

        return render_template('user_dashboard.html', booking_data=booking_data, enumerate=enumerate)
    else:
        return "Invalid request method",405


# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        mobile = request.form['mobile']
        address = request.form['address']
        password = hashlib.md5(request.form['password'].encode()).hexdigest()  # Hash password

        # Generate a random customer ID
        customer_id = random.randint(100000, 999999)

        # Insert user data into the database
        cursor = get_db().cursor()
        cursor.execute('''
            INSERT INTO customer (id, full_name, email, mobile, address, password)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (customer_id, full_name, email, mobile, address, password))
        get_db().commit()

        # Return customer ID as JSON response
        return jsonify({'customerID': customer_id})
    else:
        # Handle GET request (if needed)
        return render_template('register.html')

# Admin Orders
@app.route('/admin/orders')
def admin_orders():
    if 'admin_logged_in' not in session:
        return redirect('/admin/login')

    # Fetch orders from the database
    cursor = get_db().cursor()
    cursor.execute('SELECT * FROM booking WHERE status = "waiting"')
    orders = cursor.fetchall()

    return render_template('admin_orders.html', orders=orders)

# Admin Current Orders
@app.route('/admin/current_orders')
def admin_current_orders():
    if 'admin_logged_in' not in session:
        return redirect('/admin/login')  # Redirect to admin login if not logged in

    # Query database for bookings with status "waiting"
    cursor = get_db().cursor()
    cursor.execute('SELECT * FROM booking WHERE status = "approved"')
    current_orders = cursor.fetchall()

    return render_template('current_orders.html', current_orders=current_orders)

# Route to view old orders
@app.route('/admin/old_orders')
def old_orders():
    if 'admin_logged_in' not in session:
        return redirect('/admin/login')  # Redirect to admin login page if admin is not logged in

    # Fetch old orders from the database (assuming "completed" and "declined" statuses are considered old)
    cursor = get_db().cursor()
    cursor.execute('SELECT * FROM booking WHERE status = "completed"')
    orders = cursor.fetchall()

    return render_template('old_orders.html', orders=orders)


#approve or decline order
@app.route('/admin/orders/<int:order_id>', methods=['POST'])
def admin_orders_action(order_id):
    if 'admin_logged_in' not in session:
        return redirect('/admin/login')  # Redirect to admin login page if admin is not logged in

    if request.method == 'POST':
        action = request.form['action']  # Get the action (approve or decline)
        
        # Update the status of the booking based on the action
        cursor = get_db().cursor()
        if action == 'approve':
            cursor.execute('UPDATE booking SET status = ? WHERE id = ?', ('Approved', order_id))
        elif action == 'decline':
            cursor.execute('UPDATE booking SET status = ? WHERE id = ?', ('Declined', order_id))
        
        # Commit the changes to the database
        get_db().commit()

        return redirect('/admin/orders')  # Redirect back to the admin orders page

# Route to mark a booking as completed
@app.route('/admin/orders/<int:order_id>/complete', methods=['POST'])
def complete_booking(order_id):
    if 'admin_logged_in' not in session:
        return redirect('/admin/login')  # Redirect to admin login page if admin is not logged in

    if request.method == 'POST':
        # Update the status of the booking to "completed"
        cursor = get_db().cursor()
        cursor.execute('UPDATE booking SET status = ? WHERE id = ?', ('Completed', order_id))

        # Commit the changes to the database
        get_db().commit()

        return redirect('/admin/orders')  # Redirect back to the admin orders page

# Admin Logout
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)  # Clear admin session
    return redirect('/')  # Redirect to admin login page

@app.route('/logout')
def logout():
    # Clear the session data
    session.clear()
    # Redirect to the login page or any other desired page after logout
    return redirect(url_for('login'))

@app.route('/review')
def review():
    return render_template('review.html')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']

        # Check if the email exists in the database
        cursor = get_db().cursor()
        cursor.execute('SELECT * FROM customer WHERE email = ?', (email,))
        user = cursor.fetchone()

        if user:
            customer_id = user[0]
            password = user[5]

            # Send email with customer ID and password
            send_email(email, customer_id, password)

            # Notify the user that the email has been sent
            flash('Your customer ID and password have been sent to your email address.', 'success')
            return redirect('/login')
        else:
            flash('Email address not found. Please enter a valid email address.', 'error')

    return render_template('forgot_password.html')

def send_email(email, customer_id, password):
    # Email configuration
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587  # Example port, adjust as necessary
    smtp_username = 'try.gpt1310@gmail.com'
    smtp_password = 'lduc lbvo napo rsei'

    # Create message container - the correct MIME type is multipart/alternative
    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = email
    msg['Subject'] = 'Your Account Details'

    # Create the body of the message (a plain-text and an HTML version)
    body = f"Your customer ID: {customer_id}\nYour password: {password}"

    # Attach the body to the message
    msg.attach(MIMEText(body, 'plain'))

    # Start the SMTP session and send the email
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(smtp_username, email, msg.as_string())

# Driver View Pending Requests
@app.route('/driver/pending_requests')
def driver_pending_requests():
    # Fetch driver information
    cursor = get_db().cursor()
    cursor.execute('SELECT * FROM driver')
    driver_info = cursor.fetchone()  # Fetch the single driver

    # Fetch pending requests assigned to the driver
    cursor.execute('SELECT * FROM booking WHERE status = "driver_pending"')
    pending_requests = cursor.fetchall()

    return render_template('driver_pending_requests.html', driver_info=driver_info, pending_requests=pending_requests)

# Route for accepting a request
@app.route('/driver/accept_request/<int:booking_id>', methods=['POST'])
def accept_request(booking_id):

    # Update the status of the booking to "accepted" in the database
    cursor = get_db().cursor()
    cursor.execute('UPDATE booking SET status = "waiting" WHERE id = ?', (booking_id,))
    get_db().commit()

    # Redirect back to the pending requests page
    return redirect('/driver/pending_requests')

# Route for declining a request
@app.route('/driver/decline_request/<int:booking_id>', methods=['POST'])
def decline_request(booking_id):

    # Update the status of the booking to "declined" in the database
    cursor = get_db().cursor()
    cursor.execute('UPDATE booking SET status = "declined" WHERE id = ?', (booking_id,))
    get_db().commit()

    # Redirect back to the pending requests page
    return redirect('/driver/pending_requests')

if __name__ == '__main__':
    app.run(host="0.0.0.0",port=5000)
