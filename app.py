from flask import Flask, render_template, request, redirect, url_for, flash, session
import pyodbc
import os
from werkzeug.utils import secure_filename
import json
import pandas as pd
from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import io
from flask_mail import Mail, Message
from datetime import date

app = Flask(__name__)

# ==========================
# Email Configuration
# ==========================

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "divitameshram11@gmail.com"
app.config["MAIL_PASSWORD"] = "fvpotnlmnfmlfblj"

mail = Mail(app)

app.secret_key = "salesanalytics123"

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

#----------------
#sql server connection
#----------------
def get_db_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=LAPTOP-PAVILION\\SQLEXPRES;"
        "DATABASE=SalesAnalyticsDB;"
        "Trusted_Connection=yes;"
    )

#----------------
#Home Page
#----------------
@app.route("/")
def home():
    return render_template("index.html")

#----------------
# Registration
#----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        firstname = request.form.get("firstname")
        lastname = request.form.get("lastname")
        username = request.form.get("username")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM RegistrationTable WHERE Username=?", (username,))
        user = cursor.fetchone()

        if user:

            flash("Username already exists. Please login.", "warning")
            return redirect(url_for("login"))

        cursor.execute("""
            INSERT INTO RegistrationTable
            (FirstName, LastName, Username, Email, PhoneNumber, Password)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
        firstname,
        lastname,
        username,
        email,
        phone,
        password)

        conn.commit()

        flash("Registration Successful. Please Login.", "success")

        return redirect(url_for("login"))

    return render_template("registration.html")

#----------------
# Login
#----------------
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM RegistrationTable
            WHERE Username=? AND Password=?
        """, (username, password))

        user = cursor.fetchone()

        conn.close()

        if user:

            session['user'] = username      # IMPORTANT

            return redirect(url_for('dashboard'))

        else:

            flash("Invalid username or password")

    return render_template("login.html")

# ----------------
# Dashboard page
# ----------------

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # ==========================
    # Dashboard Cards
    # ==========================

    cursor.execute("SELECT COUNT(*) FROM Customers")
    total_customers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Products")
    total_products = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Orders")
    total_orders = cursor.fetchone()[0]

    cursor.execute("SELECT ISNULL(SUM(TotalAmount),0) FROM Orders")
    total_revenue = cursor.fetchone()[0]

    # ==========================
    # Low Stock Products
    # ==========================

    cursor.execute("""
        SELECT ProductName, Brand, StockQuantity
        FROM Products
        WHERE StockQuantity <= 5
        ORDER BY StockQuantity ASC
    """)

    low_stock_products = cursor.fetchall()
    low_stock_count = len(low_stock_products)

    # ==========================
    # Recent Orders
    # ==========================

    cursor.execute("""
        SELECT TOP 5
            o.OrderID,
            c.CustomerName,
            p.ProductName,
            o.TotalAmount
        FROM Orders o
        JOIN Customers c
            ON o.CustomerID = c.CustomerID
        JOIN Products p
            ON o.ProductID = p.ProductID
        ORDER BY o.OrderDate DESC
    """)

    recent_orders = cursor.fetchall()

    # ==========================
    # Top Selling Products
    # ==========================

    cursor.execute("""
        SELECT TOP 5
            p.ProductName,
            p.Category,
            SUM(o.Quantity) AS QuantitySold,
            SUM(o.TotalAmount) AS Revenue
        FROM Orders o
        JOIN Products p
            ON o.ProductID = p.ProductID
        GROUP BY p.ProductName, p.Category
        ORDER BY QuantitySold DESC
    """)

    top_products = cursor.fetchall()

    # ==========================
    # Monthly Revenue Graph
    # ==========================

    cursor.execute("""
        SELECT
            MONTH(OrderDate) AS MonthNo,
            SUM(TotalAmount) AS Revenue
        FROM Orders
        GROUP BY MONTH(OrderDate)
        ORDER BY MonthNo
    """)

    monthly_data = cursor.fetchall()

    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]

    revenue_values = [0] * 12

    for row in monthly_data:
        revenue_values[row.MonthNo - 1] = float(row.Revenue)

    revenue_labels = months

    # ==========================
    # Today's Orders
    # ==========================

    cursor.execute("""
    SELECT COUNT(*)
    FROM Orders
    WHERE CAST(OrderDate AS DATE) = CAST(GETDATE() AS DATE)
    """)

    todays_orders = cursor.fetchone()[0]

    # ==========================
    # Today's Revenue
    # ==========================

    cursor.execute("""
    SELECT ISNULL(SUM(TotalAmount),0)
    FROM Orders
    WHERE CAST(OrderDate AS DATE) = CAST(GETDATE() AS DATE)
    """)

    todays_revenue = cursor.fetchone()[0]

    # ==========================
    # Revenue Growth
    # ==========================

    cursor.execute("""
    SELECT ISNULL(SUM(TotalAmount),0)
    FROM Orders
    WHERE MONTH(OrderDate)=MONTH(DATEADD(MONTH,-1,GETDATE()))
    AND YEAR(OrderDate)=YEAR(DATEADD(MONTH,-1,GETDATE()))
    """)

    last_month_revenue = cursor.fetchone()[0]

    cursor.execute("""
    SELECT ISNULL(SUM(TotalAmount),0)
    FROM Orders
    WHERE MONTH(OrderDate)=MONTH(GETDATE())
    AND YEAR(OrderDate)=YEAR(GETDATE())
    """)

    current_month_revenue = cursor.fetchone()[0]

    if last_month_revenue > 0:
        revenue_growth = round(
            ((current_month_revenue - last_month_revenue) / last_month_revenue) * 100, 1
        )
    else:
        revenue_growth = 0

    # ==========================
    # Orders Growth
    # ==========================

    cursor.execute("""
    SELECT COUNT(*)
    FROM Orders
    WHERE MONTH(OrderDate)=MONTH(DATEADD(MONTH,-1,GETDATE()))
    AND YEAR(OrderDate)=YEAR(DATEADD(MONTH,-1,GETDATE()))
    """)

    last_month_orders = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM Orders
    WHERE MONTH(OrderDate)=MONTH(GETDATE())
    AND YEAR(OrderDate)=YEAR(GETDATE())
    """)

    current_month_orders = cursor.fetchone()[0]

    if last_month_orders > 0:
        orders_growth = round(
            ((current_month_orders - last_month_orders) / last_month_orders) * 100, 1
        )
    else:
        orders_growth = 0

    # ==========================
    # Customer Growth
    # (Customer table uses CreatedDate)
    # ==========================

    cursor.execute("""
    SELECT COUNT(*)
    FROM Customers
    WHERE MONTH(CreatedDate)=MONTH(DATEADD(MONTH,-1,GETDATE()))
    AND YEAR(CreatedDate)=YEAR(DATEADD(MONTH,-1,GETDATE()))
    """)

    last_month_customers = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM Customers
    WHERE MONTH(CreatedDate)=MONTH(GETDATE())
    AND YEAR(CreatedDate)=YEAR(GETDATE())
    """)

    current_month_customers = cursor.fetchone()[0]

    if last_month_customers > 0:
        customers_growth = round(
            ((current_month_customers - last_month_customers) / last_month_customers) * 100, 1
        )
    else:
        customers_growth = 0

    # ==========================
    # Product Growth
    # (Products table uses AddedDate)
    # ==========================

    cursor.execute("""
    SELECT COUNT(*)
    FROM Products
    WHERE MONTH(AddedDate)=MONTH(DATEADD(MONTH,-1,GETDATE()))
    AND YEAR(AddedDate)=YEAR(DATEADD(MONTH,-1,GETDATE()))
    """)

    last_month_products = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM Products
    WHERE MONTH(AddedDate)=MONTH(GETDATE())
    AND YEAR(AddedDate)=YEAR(GETDATE())
    """)

    current_month_products = cursor.fetchone()[0]

    if last_month_products > 0:
        products_growth = round(
            ((current_month_products - last_month_products) / last_month_products) * 100, 1
        )
    else:
        products_growth = 0


    # ==========================
    # State Wise Sales
    # ==========================

    cursor.execute("""
        SELECT
            c.State,
            SUM(o.TotalAmount) AS Revenue
        FROM Orders o
        JOIN Customers c
            ON o.CustomerID = c.CustomerID
        GROUP BY c.State
        ORDER BY Revenue DESC
    """)

    state_sales = cursor.fetchall()

    # 👇 HE ETH ADD KAR
    category_labels = ["Electronics", "Accessories"]
    category_values = [75, 25]

    conn.close()

    return render_template(
        "dashboard.html",

        username=session["user"],

        total_customers=total_customers,
        total_products=total_products,
        total_orders=total_orders,
        total_revenue=total_revenue,

        revenue_growth=revenue_growth,
        orders_growth=orders_growth,
        customers_growth=customers_growth,
        products_growth=products_growth,

        todays_orders=todays_orders,
        todays_revenue=todays_revenue,

        current_month_revenue=current_month_revenue,
        current_month_orders=current_month_orders,
        current_month_customers=current_month_customers,
        current_month_products=current_month_products,

        low_stock_products=low_stock_products,
        low_stock_count=low_stock_count,

        recent_orders=recent_orders,
        top_products=top_products,

        revenue_labels=revenue_labels,
        revenue_values=revenue_values,

        state_sales=state_sales
    )

# -----------------------
# Add Customer
# -----------------------
@app.route("/add_customer", methods=["GET", "POST"])
def add_customer():

    if request.method == "POST":

        customer_name = request.form.get("customer_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        gender = request.form.get("gender")
        city = request.form.get("city")
        state = request.form.get("state")

        # Database Connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO Customers
            (CustomerName, Email, Phone, Gender, City, State)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            customer_name,
            email,
            phone,
            gender,
            city,
            state
        ))

        conn.commit()

        # Send Email
        send_email(
            email,
            "🎉 Welcome to Sales Analytics Management System",
            f"""
        👋 Hello {customer_name},

        ✅ Your registration has been completed successfully.

        🎊 Welcome to the Sales Analytics Management System!

        📊 You can now manage:
        • Customers
        • Products
        • Orders
        • Reports
        • Analytics

        🙏 Thank you for joining us.

        Have a great day! 😊

        ----------------------------------------
        📧 Sales Analytics Management System
        💻 Developed using Python Flask & SQL Server
        ----------------------------------------
        """
        )


        cursor.execute("SELECT CAST(SCOPE_IDENTITY() AS INT)")
        customer_id = cursor.fetchone()[0]

        add_audit_log(
            "Admin",
            "ADD",
            "Customers",
            customer_id
        )

        conn.close()

        flash("Customer Added Successfully!", "success")
        return redirect(url_for("customers"))

    return render_template("add_customer.html")



# -----------------------
# Edit Customer
# -----------------------
@app.route("/edit_customer/<int:id>", methods=["GET", "POST"])
def edit_customer(id):

    if request.method == "POST":

        customer_name = request.form.get("customer_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        gender = request.form.get("gender")
        city = request.form.get("city")
        state = request.form.get("state")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE Customers
            SET CustomerName=?,
                Email=?,
                Phone=?,
                Gender=?,
                City=?,
                State=?
            WHERE CustomerID=?
        """,
        (
            customer_name,
            email,
            phone,
            gender,
            city,
            state,
            id
        ))

        conn.commit()

        add_audit_log(
            "Admin",
            "UPDATE",
            "Customers",
            id
        )

        conn.close()

        flash("Customer Updated Successfully!", "success")

        return redirect(url_for("customers"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM Customers WHERE CustomerID=?",
        (id,)
    )


    customer = cursor.fetchone()

    return render_template(
        "edit_customer.html",
        customer=customer
    )

# -----------------------
# Delete Customer
# -----------------------
@app.route("/delete_customer/<int:id>")
def delete_customer(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM Customers WHERE CustomerID=?",
        (id,)
    )

    conn.commit()

    add_audit_log(
        "Admin",
        "DELETE",
        "Customers",
        id
    )

    conn.close()

    flash("Customer Deleted Successfully!", "success")

    return redirect(url_for("customers"))

@app.route("/customers")
def customers():

    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)

    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total Records
    cursor.execute("""
        SELECT COUNT(*)
        FROM Customers
        WHERE
            CAST(CustomerID AS VARCHAR) LIKE ?
            OR CustomerName LIKE ?
            OR Email LIKE ?
            OR City LIKE ?
    """,
    (
        '%' + search + '%',
        '%' + search + '%',
        '%' + search + '%',
        '%' + search + '%'
    ))

    total_records = cursor.fetchone()[0]

    total_pages = (total_records + per_page - 1) // per_page

    # Current Page Records
    cursor.execute("""
        SELECT *
        FROM Customers
        WHERE
            CAST(CustomerID AS VARCHAR) LIKE ?
            OR CustomerName LIKE ?
            OR Email LIKE ?
            OR City LIKE ?
        ORDER BY CustomerID DESC
        OFFSET ? ROWS
        FETCH NEXT ? ROWS ONLY
    """,
    (
        '%' + search + '%',
        '%' + search + '%',
        '%' + search + '%',
        '%' + search + '%',
        offset,
        per_page
    ))

    customers = cursor.fetchall()

    conn.close()

    return render_template(
        "customers.html",
        customers=customers,
        search=search,
        page=page,
        total_pages=total_pages
    )

# -----------------------
# Products
# -----------------------

@app.route("/products")
def products():

    search = request.args.get("search", "")
    sort = request.args.get("sort", "")
    page = request.args.get("page", 1, type=int)

    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()

    # -----------------------
    # Count Total Records
    # -----------------------

    count_query = """
        SELECT COUNT(*)
        FROM Products
        WHERE
            CAST(ProductID AS VARCHAR) LIKE ?
            OR ProductName LIKE ?
            OR Category LIKE ?
            OR Brand LIKE ?
    """

    params = (
        '%' + search + '%',
        '%' + search + '%',
        '%' + search + '%',
        '%' + search + '%'
    )

    cursor.execute(count_query, params)

    total_records = cursor.fetchone()[0]
    total_pages = (total_records + per_page - 1) // per_page

    # -----------------------
    # Main Query
    # -----------------------

    query = """
        SELECT *
        FROM Products
        WHERE
            CAST(ProductID AS VARCHAR) LIKE ?
            OR ProductName LIKE ?
            OR Category LIKE ?
            OR Brand LIKE ?
    """

    # Sorting
    if sort == "price_asc":
        query += " ORDER BY Price ASC"

    elif sort == "price_desc":
        query += " ORDER BY Price DESC"

    elif sort == "stock_asc":
        query += " ORDER BY StockQuantity ASC"

    elif sort == "stock_desc":
        query += " ORDER BY StockQuantity DESC"

    elif sort == "name":
        query += " ORDER BY ProductName ASC"

    else:
        query += " ORDER BY ProductID DESC"

    # Pagination
    query += " OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"

    cursor.execute(
        query,
        (
            '%' + search + '%',
            '%' + search + '%',
            '%' + search + '%',
            '%' + search + '%',
            offset,
            per_page
        )
    )

    products = cursor.fetchall()

    conn.close()

    return render_template(
        "products.html",
        products=products,
        search=search,
        sort=sort,
        page=page,
        total_pages=total_pages
    )


@app.route("/add_product", methods=["GET", "POST"])
def add_product():

    if request.method == "POST":

        product_name = request.form.get("product_name")
        category = request.form.get("category")
        brand = request.form.get("brand")
        price = request.form.get("price")
        stock = request.form.get("stock")
        supplier = request.form.get("supplier")

        # ---------- ADD THIS CODE HERE ----------
        image = request.files["product_image"]

        filename = ""

        if image and image.filename != "":

            filename = secure_filename(image.filename)

            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )
        # ---------- END HERE ----------

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO Products
            (
                ProductName,
                Category,
                Brand,
                Price,
                StockQuantity,
                Supplier,
                ProductImage
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            product_name,
            category,
            brand,
            price,
            stock,
            supplier,
            filename
        ))

        conn.commit()
        # Get newly inserted Product ID
        product_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]

        # Audit Log
        add_audit_log(
            "Admin",
            "ADD",
            "Products",
            product_id
        )

        conn.close()

        flash("Product Added Successfully!", "success")

        return redirect(url_for("products"))

    return render_template("add_product.html")

# -----------------------
# Edit Product
# -----------------------

@app.route("/edit_product/<int:id>", methods=["GET", "POST"])
def edit_product(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM Products WHERE ProductID=?",
        (id,)
    )

    product = cursor.fetchone()


    if request.method == "POST":

        image = request.files["product_image"]

        filename = product.Image

        if image and image.filename != "":
            filename = secure_filename(image.filename)

            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

        product_name = request.form.get("product_name")
        category = request.form.get("category")
        brand = request.form.get("brand")
        price = request.form.get("price")
        stock = request.form.get("stock")
        supplier = request.form.get("supplier")

        cursor.execute("""
            UPDATE Products
            SET ProductName=?,
                Category=?,
                Brand=?,
                Price=?,
                StockQuantity=?,
                Supplier=?
                Image=?
            WHERE ProductID=?
        """,
        (
            product_name,
            category,
            brand,
            price,
            stock,
            supplier,
            filename,
            id
        ))

        conn.commit()

        add_audit_log(
            "Admin",
            "UPDATE",
            "Customers",
            id
        )
        conn.close()

        flash("Product Updated Successfully!", "success")

        return redirect(url_for("products"))

    conn.close()

    return render_template(
        "edit_product.html",
        product=product
    )

# -----------------------
# Delete Product
# -----------------------

@app.route("/delete_product/<int:id>")
def delete_product(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM Products WHERE ProductID=?",
        (id,)
    )

    conn.commit()
    add_audit_log(
        "Admin",
        "DELETE",
        "Customers",
        id
    )
    conn.close()

    flash("Product Deleted Successfully!", "success")

    return redirect(url_for("products"))


# -----------------------
# Orders
# -----------------------

@app.route("/sales")
def sales():

    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)

    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()

    # -----------------------
    # Count Total Records
    # -----------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM Orders o
        INNER JOIN Customers c
            ON o.CustomerID = c.CustomerID
        INNER JOIN Products p
            ON o.ProductID = p.ProductID
        WHERE
            c.CustomerName LIKE ?
            OR p.ProductName LIKE ?
    """,
    (
        '%' + search + '%',
        '%' + search + '%'
    ))

    total_records = cursor.fetchone()[0]
    total_pages = (total_records + per_page - 1) // per_page

    # -----------------------
    # Fetch Orders
    # -----------------------

    cursor.execute("""
        SELECT
            o.OrderID,
            c.CustomerName,
            p.ProductName,
            o.Quantity,
            o.TotalAmount,
            o.OrderDate

        FROM Orders o

        INNER JOIN Customers c
            ON o.CustomerID = c.CustomerID

        INNER JOIN Products p
            ON o.ProductID = p.ProductID

        WHERE
            c.CustomerName LIKE ?
            OR p.ProductName LIKE ?

        ORDER BY o.OrderID DESC

        OFFSET ? ROWS
        FETCH NEXT ? ROWS ONLY
    """,
    (
        '%' + search + '%',
        '%' + search + '%',
        offset,
        per_page
    ))

    orders = cursor.fetchall()

    conn.close()

    return render_template(
        "orders.html",
        orders=orders,
        search=search,
        page=page,
        total_pages=total_pages
    )



# -----------------------
# Add Order
# -----------------------

@app.route("/add_order", methods=["GET", "POST"])
def add_order():

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        customer_id = request.form["customer_id"]
        product_id = request.form["product_id"]
        quantity = int(request.form["quantity"])
        order_date = request.form["order_date"]

        # Get Product Price
        cursor.execute("""
            SELECT Price, StockQuantity
            FROM Products
            WHERE ProductID = ?
        """, (product_id,))

        product = cursor.fetchone()

        price = float(product.Price)
        stock = product.StockQuantity

        # Check Stock
        if quantity > stock:
            flash("Not enough stock available!", "danger")
            return redirect(url_for("add_order"))

        total_amount = price * quantity

        # Save Order
        cursor.execute("""
            INSERT INTO Orders
            (CustomerID, ProductID, Quantity, TotalAmount, OrderDate)
            VALUES (?, ?, ?, ?, ?)
        """,
        (
            customer_id,
            product_id,
            quantity,
            total_amount,
            order_date
        ))

        # Reduce Stock
        cursor.execute("""
            UPDATE Products
            SET StockQuantity = StockQuantity - ?
            WHERE ProductID = ?
        """,
        (
            quantity,
            product_id
        ))

        conn.commit()

        add_audit_log(
            "Admin",
            "ADD",
            "Orders",
            customer_id
        )

        conn.close()

        flash("Order Added Successfully!", "success")

        return redirect(url_for("sales"))

    # Load Customers
    cursor.execute("""
        SELECT CustomerID, CustomerName
        FROM Customers
        ORDER BY CustomerName
    """)
    customers = cursor.fetchall()

    # Load Products with all details
    cursor.execute("""
        SELECT
            ProductID,
            ProductName,
            Category,
            Brand,
            Supplier,
            Price,
            StockQuantity
        FROM Products
        ORDER BY ProductName
    """)
    products = cursor.fetchall()

    conn.close()

    return render_template(
        "add_order.html",
        customers=customers,
        products=products,
        today=date.today().strftime("%Y-%m-%d")
    )


# -----------------------
# Edit Order
# -----------------------

@app.route("/edit_order/<int:id>", methods=["GET", "POST"])
def edit_order(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        customer_id = request.form.get("customer_id")
        product_id = request.form.get("product_id")
        quantity = int(request.form.get("quantity"))
        order_date = request.form.get("order_date")

        # Get Product Price
        cursor.execute(
            "SELECT Price FROM Products WHERE ProductID=?",
            (product_id,)
        )

        product = cursor.fetchone()

        total_amount = product.Price * quantity

        cursor.execute("""
            UPDATE Orders
            SET CustomerID=?,
                ProductID=?,
                Quantity=?,
                TotalAmount=?,
                OrderDate=?
            WHERE OrderID=?
        """,
        (
            customer_id,
            product_id,
            quantity,
            total_amount,
            order_date,
            id
        ))

        conn.commit()

        add_audit_log(
            "Admin",
            "UPDATE",
            "Customers",
            id
        )

        conn.close()

        flash("Order Updated Successfully!", "success")

        return redirect(url_for("sales"))

    # Load Customers
    cursor.execute("SELECT CustomerID, CustomerName FROM Customers")
    customers = cursor.fetchall()

    # Load Products
    cursor.execute("SELECT ProductID, ProductName FROM Products")
    products = cursor.fetchall()

    # Load Order
    cursor.execute(
        "SELECT * FROM Orders WHERE OrderID=?",
        (id,)
    )

    order = cursor.fetchone()

    return render_template(
        "edit_order.html",
        customers=customers,
        products=products,
        order=order
    )

# -----------------------
# Delete Order
# -----------------------

@app.route("/delete_order/<int:id>")
def delete_order(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM Orders WHERE OrderID=?",
        (id,)
    )

    conn.commit()
    add_audit_log(
        "Admin",
        "DELETE",
        "Customers",
        id
    )
    conn.close()

    flash("Order Deleted Successfully!", "success")

    return redirect(url_for("sales"))


# -----------------------
# Reports
# -----------------------

@app.route("/reports")
def reports():

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total Revenue
    cursor.execute("SELECT ISNULL(SUM(TotalAmount),0) FROM Orders")
    total_revenue = cursor.fetchone()[0]

    # Total Orders
    cursor.execute("SELECT COUNT(*) FROM Orders")
    total_orders = cursor.fetchone()[0]

    # Total Customers
    cursor.execute("SELECT COUNT(*) FROM Customers")
    total_customers = cursor.fetchone()[0]

    # Total Products
    cursor.execute("SELECT COUNT(*) FROM Products")
    total_products = cursor.fetchone()[0]

    # Average Order
    cursor.execute("SELECT ISNULL(AVG(TotalAmount),0) FROM Orders")
    avg_order = cursor.fetchone()[0]

    # Customer Sales Summary
    cursor.execute("""
        SELECT
            C.CustomerName,
            COUNT(O.OrderID) AS Orders,
            ISNULL(SUM(O.TotalAmount),0) AS TotalSales
        FROM Customers C
        LEFT JOIN Orders O
            ON C.CustomerID = O.CustomerID
        GROUP BY C.CustomerName
        ORDER BY TotalSales DESC
    """)

    reports = cursor.fetchall()

    conn.close()

    return render_template(
        "reports.html",
        total_revenue=total_revenue,
        total_orders=total_orders,
        total_customers=total_customers,
        total_products=total_products,
        avg_order=avg_order,
        reports=reports
    )


# ==========================================================
# EXPORT CUSTOMERS EXCEL
# ==========================================================

@app.route("/export/customers/excel")
def export_customers_excel():

    conn = get_db_connection()

    query = """
    SELECT
        CustomerID,
        CustomerName,
        Email,
        Phone,
        Gender,
        City,
        State
    FROM Customers
    """

    df = pd.read_sql(query, conn)

    conn.close()

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Customers")

    output.seek(0)

    return send_file(
        output,
        download_name="Customers_Report.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ==========================================================
# EXPORT PRODUCTS EXCEL
# ==========================================================

@app.route("/export/products/excel")
def export_products_excel():

    conn = get_db_connection()

    query = """
    SELECT
        ProductID,
        ProductName,
        Category,
        Brand,
        Price,
        StockQuantity,
        Supplier
    FROM Products
    """

    df = pd.read_sql(query, conn)

    conn.close()

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Products")

    output.seek(0)

    return send_file(
        output,
        download_name="Products_Report.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ==========================================================
# EXPORT ORDERS EXCEL
# ==========================================================

@app.route("/export/orders/excel")
def export_orders_excel():

    conn = get_db_connection()

    query = """
    SELECT
        OrderID,
        CustomerID,
        ProductID,
        Quantity,
        TotalAmount,
        OrderDate
    FROM Orders
    """

    df = pd.read_sql(query, conn)

    conn.close()

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Orders")

    output.seek(0)

    return send_file(
        output,
        download_name="Orders_Report.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ==========================================================
# PDF ROUTES (Coming Next)
# ==========================================================

@app.route("/export/customers/pdf")
def export_customers_pdf():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            CustomerID,
            CustomerName,
            Email,
            Phone,
            City
        FROM Customers
        ORDER BY CustomerID
    """)

    rows = cursor.fetchall()
    conn.close()

    buffer = io.BytesIO()

    pdf = SimpleDocTemplate(buffer)

    data = [
        ["ID", "Customer Name", "Email", "Phone", "City"]
    ]

    for row in rows:
        data.append([
            row.CustomerID,
            row.CustomerName,
            row.Email,
            row.Phone,
            row.City
        ])

    table = Table(data)

    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.grey),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),

        ('GRID',(0,0),(-1,-1),1,colors.black),

        ('BACKGROUND',(0,1),(-1,-1),colors.beige),

        ('ALIGN',(0,0),(-1,-1),'CENTER'),

        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),

        ('BOTTOMPADDING',(0,0),(-1,0),12),
    ]))

    pdf.build([table])

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="Customers_Report.pdf",
        mimetype="application/pdf"
    )

@app.route("/export/products/pdf")
def export_products_pdf():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            ProductID,
            ProductName,
            Category,
            Brand,
            Price,
            StockQuantity,
            Supplier
        FROM Products
    """)

    rows = cursor.fetchall()
    conn.close()

    buffer = io.BytesIO()

    pdf = SimpleDocTemplate(buffer)

    data = [["ID","Product","Category","Price","Stock"]]

    for row in rows:
        data.append([
            row.ProductID,
            row.ProductName,
            row.Category,
            row.Brand,
            row.Price,
            row.StockQuantity,
            row.Supplier
        ])

    table = Table(data)

    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.darkblue),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),1,colors.black),
        ('BACKGROUND',(0,1),(-1,-1),colors.beige),
        ('ALIGN',(0,0),(-1,-1),'CENTER')
    ]))

    pdf.build([table])

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="Products_Report.pdf",
        mimetype="application/pdf"
    )

@app.route("/export/orders/pdf")
def export_orders_pdf():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            OrderID,
            CustomerID,
            ProductID,
            Quantity,
            TotalAmount
        FROM Orders
    """)

    rows = cursor.fetchall()
    conn.close()

    buffer = io.BytesIO()

    pdf = SimpleDocTemplate(buffer)

    data = [["Order ID","Customer","Product","Qty","Total"]]

    for row in rows:
        data.append([
            row.OrderID,
            row.CustomerID,
            row.ProductID,
            row.Quantity,
            row.TotalAmount
        ])

    table = Table(data)

    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.green),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),1,colors.black),
        ('BACKGROUND',(0,1),(-1,-1),colors.beige),
        ('ALIGN',(0,0),(-1,-1),'CENTER')
    ]))

    pdf.build([table])

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="Orders_Report.pdf",
        mimetype="application/pdf"
    )


# -----------------------
# Analytics
# -----------------------

@app.route("/analytics")
def analytics():

    conn = get_db_connection()
    cursor = conn.cursor()

    # -----------------------
    # Monthly Revenue
    # -----------------------

    cursor.execute("""
        SELECT
            DATENAME(MONTH, OrderDate) AS Month,
            SUM(TotalAmount) AS TotalSales
        FROM Orders
        GROUP BY
            MONTH(OrderDate),
            DATENAME(MONTH, OrderDate)
        ORDER BY MONTH(OrderDate)
    """)

    monthly = cursor.fetchall()

    months = [row.Month for row in monthly]
    sales = [float(row.TotalSales) for row in monthly]

    # -----------------------
    # Sales by Category
    # -----------------------

    cursor.execute("""
        SELECT
            P.Category,
            SUM(O.TotalAmount) AS TotalSales
        FROM Orders O
        INNER JOIN Products P
            ON O.ProductID = P.ProductID
        GROUP BY P.Category
    """)

    category = cursor.fetchall()

    category_name = [row.Category for row in category]
    category_sales = [float(row.TotalSales) for row in category]

    # -----------------------
    # Top 5 Selling Products
    # -----------------------

    cursor.execute("""
        SELECT TOP 5
            P.ProductName,
            COUNT(O.OrderID) AS TotalSold
        FROM Orders O
        INNER JOIN Products P
            ON O.ProductID = P.ProductID
        GROUP BY P.ProductName
        ORDER BY TotalSold DESC
    """)

    products = cursor.fetchall()

    top_products = [row.ProductName for row in products]
    top_sales = [row.TotalSold for row in products]

    # -----------------------
    # Customer Growth
    # -----------------------

    cursor.execute("""
        SELECT
            DATENAME(MONTH, CreatedDate) AS Month,
            COUNT(CustomerID) AS TotalCustomers
        FROM Customers
        GROUP BY
            MONTH(CreatedDate),
            DATENAME(MONTH, CreatedDate)
        ORDER BY MONTH(CreatedDate)
    """)

    customers = cursor.fetchall()

    customer_months = [row.Month for row in customers]
    customer_growth = [row.TotalCustomers for row in customers]

    conn.close()

    return render_template(
        "analytics.html",

        months=months,
        sales=sales,

        category_name=category_name,
        category_sales=category_sales,

        top_products=top_products,
        top_sales=top_sales,

        customer_months=customer_months,
        customer_growth=customer_growth
    )


@app.route("/customer_history/<int:id>")
def customer_history(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    # Customer Information
    cursor.execute("""
        SELECT *
        FROM Customers
        WHERE CustomerID=?
    """, (id,))

    customer = cursor.fetchone()

    # Purchase History
    cursor.execute("""
        SELECT
            O.OrderID,
            P.ProductName,
            O.Quantity,
            O.TotalAmount,
            O.OrderDate
        FROM Orders O
        INNER JOIN Products P
            ON O.ProductID = P.ProductID
        WHERE O.CustomerID=?
        ORDER BY O.OrderDate DESC
    """, (id,))

    orders = cursor.fetchall()

    # Total Orders
    cursor.execute("""
        SELECT COUNT(*)
        FROM Orders
        WHERE CustomerID=?
    """, (id,))

    total_orders = cursor.fetchone()[0]

    # Total Spending
    cursor.execute("""
        SELECT ISNULL(SUM(TotalAmount),0)
        FROM Orders
        WHERE CustomerID=?
    """, (id,))

    total_spent = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "customer_history.html",
        customer=customer,
        orders=orders,
        total_orders=total_orders,
        total_spent=total_spent
    )
@app.route("/invoice/<int:id>")
def generate_invoice(id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            O.OrderID,
            O.OrderDate,
            O.Quantity,
            O.TotalAmount,

            C.CustomerName,
            C.Email,
            C.Phone,

            P.ProductName,
            P.Price

        FROM Orders O

        INNER JOIN Customers C
            ON O.CustomerID = C.CustomerID

        INNER JOIN Products P
            ON O.ProductID = P.ProductID

        WHERE O.OrderID=?
    """,(id,))

    order = cursor.fetchone()

    conn.close()

    buffer = io.BytesIO()

    pdf = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()

    elements=[]

    elements.append(
        Paragraph("<b>Sales Analytics Management System</b>",styles["Title"])
    )

    elements.append(
        Paragraph("Invoice",styles["Heading2"])
    )

    data=[

        ["Invoice No",order.OrderID],
        ["Customer",order.CustomerName],
        ["Email",order.Email],
        ["Phone",order.Phone],
        ["Product",order.ProductName],
        ["Quantity",order.Quantity],
        ["Price","₹{}".format(order.Price)],
        ["Total","₹{}".format(order.TotalAmount)],
        ["Order Date",str(order.OrderDate)]

    ]

    table=Table(data,colWidths=[170,250])

    table.setStyle(TableStyle([

        ('GRID',(0,0),(-1,-1),1,colors.black),

        ('BACKGROUND',(0,0),(0,-1),colors.lightgrey),

        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),

        ('BOTTOMPADDING',(0,0),(-1,-1),8)

    ]))

    elements.append(table)

    pdf.build(elements)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Invoice_{id}.pdf",
        mimetype="application/pdf"
    )

def add_audit_log(username, action, table_name, record_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO AuditLogs
            (Username, ActionType, TableName, RecordID)
            VALUES (?, ?, ?, ?)
        """, (username, action, table_name, record_id))

        conn.commit()
        print("Audit Log Inserted Successfully")

    except Exception as e:
        print("Audit Log Error:", e)

    finally:
        conn.close()


@app.route("/auditlogs")
def audit_logs():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM AuditLogs
        ORDER BY ActionDate DESC
    """)

    logs = cursor.fetchall()

    conn.close()

    return render_template(
        "auditlogs.html",
        logs=logs
    )


def send_email(receiver, subject, body):

    msg = Message(
        subject,
        sender=app.config["MAIL_USERNAME"],
        recipients=[receiver]
    )

    print("Sending email...")

    msg.body = body

    mail.send(msg)

    print("Email sent successfully")




@app.route("/logout")
def logout():
    return render_template("login.html")


if __name__ == "__main__":
    app.run(debug=True)