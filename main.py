import sqlite3

# connect to the database
conn = sqlite3.connect('marketing_app.db')
cursor = conn.cursor()

# create tables in the database
cursor.execute('''CREATE TABLE IF NOT EXISTS shop_owners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    store_name TEXT,
                    password TEXT,
                    security_question1 TEXT,
                    security_answer1 TEXT,
                    security_question2 TEXT,
                    security_answer2 TEXT,
                    role INTEGER
                )''')

cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    password TEXT,
                    security_question1 TEXT,
                    security_answer1 TEXT,
                    security_question2 TEXT,
                    security_answer2 TEXT
                )''')

cursor.execute('''CREATE TABLE IF NOT EXISTS commodities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shop_owner_id INTEGER,
                    name TEXT,
                    price REAL,
                    description TEXT,
                    FOREIGN KEY (shop_owner_id) REFERENCES shop_owners (id)
                )''')

cursor.execute('''CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    commodity_id INTEGER,
                    customer_id INTEGER,
                    comment TEXT,
                    FOREIGN KEY (commodity_id) REFERENCES commodities (id),
                    FOREIGN KEY (customer_id) REFERENCES customers (id)
                )''')

cursor.execute('''CREATE TABLE IF NOT EXISTS replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comment_id INTEGER,
                    shop_owner_id INTEGER,
                    reply TEXT,
                    FOREIGN KEY (comment_id) REFERENCES comments (id),
                    FOREIGN KEY (shop_owner_id) REFERENCES shop_owners (id)
                )''')

# Shop owner sign-up
def shop_owner_signup():
    name = input("Enter your name: ")
    store_name = input("Enter your store name: ")
    password = input("Enter your password: ")
    security_question1 = input("Enter your first security question: ")
    security_answer1 = input("Enter the answer to your first security question: ")
    security_question2 = input("Enter your second security question: ")
    security_answer2 = input("Enter the answer to your second security question: ")
    role = 1

    # save the details in the database
    cursor.execute('''INSERT INTO shop_owners (name, store_name, password, security_question1, security_answer1, security_question2, security_answer2, role)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (name, store_name, password, security_question1, security_answer1, security_question2, security_answer2, role))
    conn.commit()

    print("Shop owner sign-up successful!")

# customer sign-up
def customer_signup():
    name = input("Enter your name: ")
    password = input("Enter your password: ")
    security_question1 = input("Enter your first security question: ")
    security_answer1 = input("Enter the answer to your first security question: ")
    security_question2 = input("Enter your second security question: ")
    security_answer2 = input("Enter the answer to your second security question: ")

    # save the details in the database
    cursor.execute('''INSERT INTO customers (name, password, security_question1, security_answer1, security_question2, security_answer2)
                      VALUES (?, ?, ?, ?, ?, ?)''', (name, password, security_question1, security_answer1, security_question2, security_answer2))
    conn.commit()

    print("Customer sign-up successful!")

# Shop owner login
def shop_owner_login():
    name = input("Enter your name: ")
    password = input("Enter your password: ")

    # Check if the credentials are correct
    cursor.execute('''SELECT * FROM shop_owners WHERE name = ? AND password = ?''', (name, password))
    shop_owner = cursor.fetchone()

    if shop_owner:
        print("Login successful!")
        print("Welcome, Shop Owner:", shop_owner[1])
        while True:
            print("Please select an option:")
            print("1. Add a commodity")
            print("2. Reply to comments")
            print("3. Exit")

            choice = input("Enter your choice (1-3): ")

            if choice == '1':
                add_commodity(shop_owner[0])
            elif choice == '2':
                reply_to_comments(shop_owner[0])
            elif choice == '3':
                break
            else:
                print("Invalid choice. Please try again.")
    else:
        print("Incorrect name or password.")

# customer login
def customer_login():
    name = input("Enter your name: ")
    password = input("Enter your password: ")

    # Check if the credentials are correct
    cursor.execute('''SELECT * FROM customers WHERE name = ? AND password = ?''', (name, password))
    customer = cursor.fetchone()

    if customer:
        print("Login successful!")
        print("Welcome, Customer:", customer[1])
        while True:
            print("Please select an option:")
            print("1. Search for commodities")
            print("2. Buy a commodity")
            print("3. Leave a comment")
            print("4. Exit")

            choice = input("Enter your choice (1-4): ")

            if choice == '1':
                search_commodities()
            elif choice == '2':
                buy_commodity(customer[0])
            elif choice == '3':
                leave_comment(customer[0])
            elif choice == '4':
                break
            else:
                print("Invalid choice. Please try again.")
    else:
        print("Incorrect name or password.")

# shop owner functionality: Add a commodity
def add_commodity(shop_owner_id):
    name = input("Enter the name of the commodity: ")
    price = float(input("Enter the price of the commodity: "))
    description = input("Enter the description of the commodity: ")

    # Save the commodity in the database
    cursor.execute('''INSERT INTO commodities (shop_owner_id, name, price, description)
                      VALUES (?, ?, ?, ?)''', (shop_owner_id, name, price, description))
    conn.commit()

    print("Commodity added successfully!")

# Shop owner functionality: Reply to comments
def reply_to_comments(shop_owner_id):
    # Retrieve all the comments without replies for the shop owner
    cursor.execute('''SELECT comments.id, comments.commodity_id, customers.name, comments.comment
                      FROM comments
                      INNER JOIN commodities ON comments.commodity_id = commodities.id
                      INNER JOIN customers ON comments.customer_id = customers.id
                      WHERE commodities.shop_owner_id = ? AND comments.id NOT IN (SELECT comment_id FROM replies)''', (shop_owner_id,))
    comments = cursor.fetchall()

    if comments:
        print("Comments without replies:")
        for comment in comments:
            print("Comment ID:", comment[0])
            print("Commodity ID:", comment[1])
            print("Customer Name:", comment[2])
            print("Comment:", comment[3])
            print()  # Print a blank line for separation

        comment_id = input("Enter the ID of the comment to reply to (or '0' to cancel): ")

        if comment_id == '0':
            return

        reply = input("Enter your reply: ")

        # Save the reply in the database
        cursor.execute('''INSERT INTO replies (comment_id, shop_owner_id, reply)
                          VALUES (?, ?, ?)''', (comment_id, shop_owner_id, reply))
        conn.commit()

        print("Reply added successfully!")
    else:
        print("No comments without replies.")

# customer functionality: Leave a comment
def leave_comment(customer_id):
    # display all available commodities
    cursor.execute('''SELECT * FROM commodities''')
    commodities = cursor.fetchall()

    if commodities:
        print("Available commodities:")
        for commodity in commodities:
            print("Commodity ID:", commodity[0])
            print("Name:", commodity[2])
            print("Price:", commodity[3])
            print("Description:", commodity[4])
            print()  # for separation

        commodity_id = input("Enter the ID of the commodity to leave a comment for (or '0' to cancel): ")

        if commodity_id == '0':
            return

        comment = input("Enter your comment: ")

        # Save the comment in the database
        cursor.execute('''INSERT INTO comments (commodity_id, customer_id, comment)
                          VALUES (?, ?, ?)''', (commodity_id, customer_id, comment))
        conn.commit()

        print("Comment added successfully!")
    else:
        print("No commodities available.")

# Search for commodities
def search_commodities():
    keyword = input("Enter a keyword to search for commodities: ")

    # search for commodities based on the keyword
    cursor.execute('''SELECT * FROM commodities WHERE name LIKE ? OR description LIKE ?''', (f"%{keyword}%", f"%{keyword}%"))
    commodities = cursor.fetchall()

    if commodities:
        print("Matching commodities:")
        for commodity in commodities:
            print("Commodity ID:", commodity[0])
            print("Name:", commodity[2])
            print("Price:", commodity[3])
            print("Description:", commodity[4])
            print()  #  for separation
    else:
        print("No matching commodities found.")

# Customer functionality: Buy a commodity
def buy_commodity(customer_id):
    # display all available commodities
    cursor.execute('''SELECT * FROM commodities''')
    commodities = cursor.fetchall()

    if commodities:
        print("Available commodities:")
        for commodity in commodities:
            print("Commodity ID:", commodity[0])
            print("Name:", commodity[2])
            print("Price:", commodity[3])
            print("Description:", commodity[4])
            print()  #  for separation

        commodity_id = input("Enter the ID of the commodity to buy (or '0' to cancel): ")

        if commodity_id == '0':
            return

        # save the purchase details in the database
        cursor.execute('''INSERT INTO purchases (commodity_id, customer_id)
                          VALUES (?, ?)''', (commodity_id, customer_id))
        conn.commit()

        print("Purchase successful!")
    else:
        print("No commodities available.")

# close the connection to the database
def close_connection():
    conn.close()

# main program
while True:
    print("Please select an option:")
    print("1. Shop owner sign-up")
    print("2. Customer sign-up")
    print("3. Shop owner login")
    print("4. Customer login")
    print("5. Exit")

    choice = input("Enter your choice (1-5): ")

    if choice == '1':
        shop_owner_signup()
    elif choice == '2':
        customer_signup()
    elif choice == '3':
        shop_owner_login()
    elif choice == '4':
        customer_login()
    elif choice == '5':
        close_connection()
        break
    else:
        print("Invalid choice. Please try again.")
