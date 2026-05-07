from fastapi import APIRouter

from database.db import get_db_conn

router = APIRouter(tags=["Diagnostics"])


@router.get("/test-db")
def test_db():
    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM leads;")
    count = cur.fetchone()["count"]

    cur.close()
    conn.close()

    return {"leads_count": count}

