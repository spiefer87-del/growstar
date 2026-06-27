import sqlite3
import time

from flask import jsonify, request


def register(app):

    @app.route("/api/diary", methods=["GET", "POST"])
    def api_diary():

        if request.method == "GET":

            db = sqlite3.connect("data.db")
            c = db.cursor()

            c.execute("""
                SELECT
                    id,
                    ts,
                    plant,
                    action,
                    ph,
                    ec,
                    amount,
                    note
                FROM diary_entries
                ORDER BY ts DESC
                LIMIT 500
            """)

            rows = c.fetchall()
            db.close()

            entries = []

            for r in rows:
                entries.append({
                    "id": r[0],
                    "ts": r[1],
                    "plant": r[2],
                    "action": r[3],
                    "ph": r[4],
                    "ec": r[5],
                    "amount": r[6],
                    "note": r[7]
                })

            return jsonify(entries)

        # =========================
        # POST
        # =========================

        data = request.json or {}

        ts = int(time.time())

        plant = data.get("plant")
        action = str(data.get("action", "")).strip()
        note = str(data.get("note", "")).strip()

        ph = data.get("ph")
        ec = data.get("ec")
        amount = data.get("amount")

        try:
            plant = int(plant) if plant is not None else None
        except Exception:
            plant = None

        try:
            ph = float(ph) if ph not in ("", None) else None
        except Exception:
            ph = None

        try:
            ec = float(ec) if ec not in ("", None) else None
        except Exception:
            ec = None

        try:
            amount = float(amount) if amount not in ("", None) else None
        except Exception:
            amount = None

        db = sqlite3.connect("data.db")
        c = db.cursor()

        c.execute("""
            INSERT INTO diary_entries (
                ts,
                plant,
                action,
                ph,
                ec,
                amount,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            ts,
            plant,
            action,
            ph,
            ec,
            amount,
            note
        ))

        db.commit()
        db.close()

        return {"status": "ok"}


    @app.route("/api/diary/<int:entry_id>", methods=["DELETE"])
    def api_diary_delete(entry_id):

        db = sqlite3.connect("data.db")
        c = db.cursor()

        c.execute(
            "DELETE FROM diary_entries WHERE id=?",
            (entry_id,)
        )

        db.commit()
        db.close()

        return {"status": "ok"}
