import sqlite3

from flask import jsonify, request


def register(app):

    @app.route("/api/plants")
    def api_plants():
        """
        Liefert nur ID + Name für Tagebuch Filter
        """
        db = sqlite3.connect("data.db")
        c = db.cursor()

        c.execute("SELECT id, name FROM plants ORDER BY id ASC")
        rows = c.fetchall()

        db.close()

        plants = {}

        for r in rows:
            pid = str(r[0])
            name = (r[1] or "").strip()
            plants[pid] = name if name else f"Pflanze {pid}"

        for i in range(1, 7):
            plants.setdefault(str(i), f"Pflanze {i}")

        return jsonify(plants)


    @app.route("/api/plants/data")
    def api_plants_data():

        db = sqlite3.connect("data.db")
        c = db.cursor()

        c.execute("""
            SELECT
                id,
                name,
                sativa,
                indica,
                seed_date,
                flower_days,
                flower_start
            FROM plants
            ORDER BY id ASC
        """)

        rows = c.fetchall()
        db.close()

        out = []

        for r in rows:
            out.append({
                "id": r[0],
                "name": r[1] or f"Pflanze {r[0]}",
                "sativa": r[2],
                "indica": r[3],
                "seed_date": r[4],
                "flower_days": r[5],
                "flower_start": r[6]
            })

        return jsonify(out)


    @app.route("/api/plants/data", methods=["POST"])
    def api_plants_data_save():

        data = request.json or {}
        plants = data.get("plants", [])

        if not isinstance(plants, list):
            return {
                "status": "error",
                "message": "plants must be a list"
            }, 400

        db = sqlite3.connect("data.db")
        c = db.cursor()

        for p in plants:

            try:
                pid = int(p.get("id"))
            except Exception:
                continue

            if pid < 1 or pid > 6:
                continue

            name = str(p.get("name") or "").strip()

            if not name:
                name = f"Pflanze {pid}"

            def to_int(v):
                if v in ("", None):
                    return None
                return int(float(v))

            def to_date(v):
                v = (v or "").strip()
                return v if v else None

            c.execute("""
                UPDATE plants
                SET
                    name=?,
                    sativa=?,
                    indica=?,
                    seed_date=?,
                    flower_days=?,
                    flower_start=?
                WHERE id=?
            """, (
                name,
                to_int(p.get("sativa")),
                to_int(p.get("indica")),
                to_date(p.get("seed_date")),
                to_int(p.get("flower_days")),
                to_date(p.get("flower_start")),
                pid
            ))

        db.commit()
        db.close()

        return {"status": "ok"}
