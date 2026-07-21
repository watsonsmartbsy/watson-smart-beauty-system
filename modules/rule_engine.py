# ==========================================
# SKIN CONDITION RULE ENGINE
# Brightness + Redness + Texture
# ==========================================


def skin_condition(
    brightness,
    redness,
    texture,
    conn
):


    rules = conn.execute(
        """
        SELECT *
        FROM rules
        """
    ).fetchall()



    for rule in rules:


        if (

            brightness >= rule['min_brightness']

            and

            brightness <= rule['max_brightness']


            and


            redness >= rule['min_redness']


            and


            redness <= rule['max_redness']


            and


           texture >= (rule['min_texture'] or 0)

            and

            texture <= (rule['max_texture'] or 999)
        ):



            if redness >= 180:


                severity = "High"


            elif redness >= 120:


                severity = "Medium"


            else:


                severity = "Low"



            return {

                "condition": rule['condition_name'],

                "advice": rule['advice'],

                "severity": severity

            }





    # BACKUP RULE IF NO DATABASE MATCH


    if redness >= 150 and texture >= 100:


        return {

            "condition": "Acne / Skin Irritation",

            "advice": "Use calming skincare products for irritated skin.",

            "severity": "High"

        }





    elif texture >= 150:


        return {

            "condition": "Dry Skin",

            "advice": "Skin texture appears rough. Use hydrating skincare products.",

            "severity": "Medium"

        }





    elif redness >= 120:


        return {

            "condition": "Sensitive Skin",

            "advice": "Use gentle products suitable for sensitive skin.",

            "severity": "Medium"

        }





    elif brightness >= 180 and texture < 100:


        return {

            "condition": "Oily Skin",

            "advice": "Use lightweight oil-control skincare products.",

            "severity": "Low"

        }





    else:


        return {

            "condition": "Normal Skin",

            "advice": "Maintain your skincare routine.",

            "severity": "Low"

        }