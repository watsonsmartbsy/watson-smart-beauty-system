print("NEW recommendation.py loaded")

def get_recommendation(condition, severity, conn):

    print("FUNCTION CALLED")
    print("Condition:", condition)
    print("Severity:", severity)
    print("Conn:", conn)

    cur = conn.cursor()

    if severity == "High":

        cur.execute(
            """
            SELECT *
            FROM products
            WHERE skin_type = %s
            ORDER BY price DESC
            LIMIT 1
            """,
            (condition,)
        )

    else:

        cur.execute(
            """
            SELECT *
            FROM products
            WHERE skin_type = %s
            ORDER BY price ASC
            LIMIT 1
            """,
            (condition,)
        )

    product = cur.fetchone()

    cur.close()

    return product
    return product
