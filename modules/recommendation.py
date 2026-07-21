print("NEW recommendation.py loaded")

def get_recommendation(condition, severity, conn):

    print("FUNCTION CALLED")
    print("Condition:", condition)
    print("Severity:", severity)
    print("Conn:", conn)

    if severity == "High":

        product = conn.execute(
            '''
            SELECT * FROM products
            WHERE skin_type = ?
            ORDER BY price DESC
            LIMIT 1
            ''',
            (condition,)
        ).fetchone()

    else:

        product = conn.execute(
            '''
            SELECT * FROM products
            WHERE skin_type = ?
            ORDER BY price ASC
            LIMIT 1
            ''',
            (condition,)
        ).fetchone()

    return product