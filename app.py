# -*- coding: utf-8 -*-
"""Cổng học tập cá nhân - bản Streamlit (Python)."""
import hashlib
import hmac
import math
from contextlib import closing
from datetime import date, datetime

import pandas as pd
import psycopg2
import streamlit as st
from psycopg2.extras import RealDictCursor

st.set_page_config(page_title="Cổng học tập cá nhân", page_icon="🎓")

# ---------------------------------------------------------------- Cơ sở dữ liệu (Supabase / PostgreSQL)
def secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return default


def connect():
    return psycopg2.connect(secret("DATABASE_URL"), connect_timeout=15)


def query(sql, params=()):
    with closing(connect()) as c, c.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql.replace("?", "%s"), params)
        return cur.fetchall()


def run(sql, params=()):
    with closing(connect()) as c:
        with c, c.cursor() as cur:
            cur.execute(sql.replace("?", "%s"), params)


SQL_DIEM = """INSERT INTO diem (mssv, ky, mon, tc, diem, ngay) VALUES (%s,%s,%s,%s,%s,%s)
ON CONFLICT (mssv, ky, mon) DO UPDATE
SET tc=EXCLUDED.tc, diem=EXCLUDED.diem, ngay=EXCLUDED.ngay"""


def luu_diem(rows):
    with closing(connect()) as c:
        with c, c.cursor() as cur:
            cur.executemany(SQL_DIEM, rows)


@st.cache_resource
def init_db():
    with closing(connect()) as c:
        with c, c.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS sv(mssv TEXT PRIMARY KEY, ten TEXT, pin_hash TEXT)")
            cur.execute(
                """CREATE TABLE IF NOT EXISTS diem(
                mssv TEXT, ky TEXT, mon TEXT, tc INTEGER, diem DOUBLE PRECISION, ngay TEXT,
                PRIMARY KEY (mssv, ky, mon))"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS mon_hoc(
                id SERIAL PRIMARY KEY, mssv TEXT, ten TEXT, tc INTEGER,
                mt DOUBLE PRECISION, han TEXT, pct INTEGER DEFAULT 0)"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS khao_sat(
                id SERIAL PRIMARY KEY, thoi_gian TEXT, ten TEXT, mssv TEXT,
                mon TEXT, diem DOUBLE PRECISION)"""
            )
    return True


def hash_pin(mssv, pin):
    raw = f"{mssv}:{pin}:{secret('SALT', 'hust-demo')}"
    return hashlib.sha256(raw.encode()).hexdigest()


def xep_loai(d):
    if d >= 8.5: return "Giỏi+"
    if d >= 7: return "Khá"
    if d >= 5.5: return "Trung bình"
    if d >= 4: return "Yếu"
    return "Kém"


def gpa(df):
    return (df["diem"] * df["tc"]).sum() / df["tc"].sum()


def days_left(han):
    return (date.fromisoformat(han) - date.today()).days if han else None


# ---------------------------------------------------------------- Đăng nhập
def login_screen():
    st.title("🎓 Cổng học tập cá nhân")
    t1, t2, t3 = st.tabs(["Sinh viên đăng nhập", "Đăng ký", "Giáo viên"])

    with t1:
        mssv = st.text_input("MSSV", key="l_mssv").strip()
        pin = st.text_input("Mã PIN", type="password", key="l_pin")
        if st.button("Đăng nhập", key="b_login"):
            r = query("SELECT * FROM sv WHERE mssv=?", (mssv,))
            if r and hmac.compare_digest(r[0]["pin_hash"], hash_pin(mssv, pin)):
                st.session_state.user = {"role": "sv", "mssv": mssv, "ten": r[0]["ten"]}
                st.rerun()
            else:
                st.error("Sai MSSV hoặc mã PIN.")

    with t2:
        ten = st.text_input("Họ và tên", key="r_ten").strip()
        mssv = st.text_input("MSSV", key="r_mssv").strip()
        pin = st.text_input("Đặt mã PIN (từ 4 ký tự)", type="password", key="r_pin")
        if st.button("Tạo tài khoản", key="b_reg"):
            if not ten or not mssv or len(pin) < 4:
                st.error("Nhập đủ họ tên, MSSV và PIN từ 4 ký tự.")
            elif query("SELECT 1 FROM sv WHERE mssv=?", (mssv,)):
                st.error("MSSV này đã đăng ký.")
            else:
                run("INSERT INTO sv VALUES (?,?,?)", (mssv, ten, hash_pin(mssv, pin)))
                st.success("Đăng ký xong. Sang tab Đăng nhập nhé.")

    with t3:
        gv_pw = secret("GV_PASSWORD")
        if not gv_pw:
            st.warning("Chưa đặt GV_PASSWORD trong Secrets nên chưa mở đăng nhập giáo viên.")
        pw = st.text_input("Mật khẩu giáo viên", type="password", key="g_pw")
        if st.button("Đăng nhập giáo viên", key="b_gv") and gv_pw:
            if hmac.compare_digest(pw, gv_pw):
                st.session_state.user = {"role": "gv"}
                st.rerun()
            else:
                st.error("Sai mật khẩu.")


# ---------------------------------------------------------------- Giáo viên
def teacher_screen():
    st.subheader("Quản lý điểm (giáo viên)")
    svs = query("SELECT mssv, ten FROM sv ORDER BY mssv")
    if not svs:
        st.info("Chưa có sinh viên nào đăng ký.")
    else:
        opts = {f"{r['mssv']} – {r['ten']}": r["mssv"] for r in svs}
        pick = opts[st.selectbox("Sinh viên", list(opts))]
        with st.form("f_diem", clear_on_submit=True):
            c1, c2 = st.columns(2)
            ky = c1.text_input("Học kỳ (VD: 2026.1)")
            mon = c2.text_input("Môn học")
            tc = c1.number_input("Số tín chỉ", 1, 10, 3)
            diem = c2.number_input("Điểm (0–10)", 0.0, 10.0, 8.0, 0.1)
            if st.form_submit_button("Lưu điểm"):
                if mon.strip():
                    luu_diem([(pick, ky.strip() or "Khác", mon.strip(), int(tc), float(diem),
                               datetime.now().strftime("%d/%m/%Y"))])
                    st.success("Đã lưu.")
                else:
                    st.error("Nhập tên môn học.")
        rows = query("SELECT ky, mon, tc, diem FROM diem WHERE mssv=? ORDER BY ky", (pick,))
        st.dataframe(pd.DataFrame([dict(r) for r in rows]), use_container_width=True)

    st.divider()
    st.subheader("Nhập nhiều điểm bằng file CSV / sao lưu")
    st.caption("Cột bắt buộc: mssv, ky, mon, tc, diem. Dùng để nhập hàng loạt hoặc khôi phục dữ liệu.")
    up = st.file_uploader("Chọn file CSV", type="csv")
    if up and st.button("Nhập file"):
        df = pd.read_csv(up)
        need = {"mssv", "ky", "mon", "tc", "diem"}
        if not need.issubset(df.columns):
            st.error("Thiếu cột: " + ", ".join(sorted(need - set(df.columns))))
        else:
            luu_diem([(str(r.mssv), str(r.ky), str(r.mon), int(r.tc), float(r.diem),
                       datetime.now().strftime("%d/%m/%Y")) for _, r in df.iterrows()])
            st.success(f"Đã nhập {len(df)} dòng.")
    allrows = query("SELECT mssv, ky, mon, tc, diem FROM diem")
    if allrows:
        csv = pd.DataFrame([dict(r) for r in allrows]).to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇ Tải toàn bộ điểm (sao lưu)", csv, "sao-luu-diem.csv", "text/csv")


# ---------------------------------------------------------------- Sinh viên
def scores_tab(mssv):
    rows = query("SELECT ky, mon, tc, diem FROM diem WHERE mssv=? ORDER BY ky", (mssv,))
    if not rows:
        st.info("Chưa có điểm nào. Khi thầy nhập điểm, bạn sẽ thấy ở đây.")
        return
    df = pd.DataFrame([dict(r) for r in rows])
    g = gpa(df)
    c1, c2 = st.columns(2)
    c1.metric("Điểm trung bình (thang 10)", f"{g:.2f}")
    c2.metric("Xếp loại", xep_loai(g))
    st.dataframe(df.rename(columns={"ky": "Kỳ", "mon": "Môn", "tc": "Tín chỉ", "diem": "Điểm"}),
                 use_container_width=True, hide_index=True)
    t = df.assign(p=df["diem"] * df["tc"]).groupby("ky").agg(p=("p", "sum"), tc=("tc", "sum"))
    t["Điểm TB"] = t["p"] / t["tc"]
    st.subheader("Điểm trung bình theo học kỳ")
    st.bar_chart(t["Điểm TB"])
    if len(t) > 1:
        d = t["Điểm TB"].iloc[-1] - t["Điểm TB"].iloc[-2]
        if d > 0.05: st.success(f"Kỳ gần nhất tăng {d:.2f} điểm so với kỳ trước.")
        elif d < -0.05: st.warning(f"Kỳ gần nhất giảm {abs(d):.2f} điểm. Hãy xem lại các môn thấp nhất.")
        else: st.info("Điểm hai kỳ gần nhất gần như không đổi.")
    st.download_button("⬇ Tải bảng điểm (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                       "bang-diem.csv", "text/csv")


def progress_tab(mssv):
    with st.form("f_mon", clear_on_submit=True):
        c1, c2 = st.columns(2)
        ten = c1.text_input("Tên môn")
        tc = c2.number_input("Tín chỉ", 1, 10, 3)
        mt = c1.number_input("Điểm mục tiêu", 0.0, 10.0, 8.0, 0.1)
        han = c2.date_input("Hạn thi / nộp bài", value=None)
        if st.form_submit_button("Thêm môn") and ten.strip():
            run("INSERT INTO mon_hoc(mssv,ten,tc,mt,han) VALUES (?,?,?,?,?)",
                (mssv, ten.strip(), int(tc), float(mt), han.isoformat() if han else ""))
            st.rerun()

    overall = st.container()
    rows = query("SELECT * FROM mon_hoc WHERE mssv=? ORDER BY id", (mssv,))
    if not rows:
        st.info("Chưa có môn nào. Hãy thêm môn ở trên.")
        return
    for m in rows:
        d = days_left(m["han"])
        tag = "" if d is None else (" · ⚠️ quá hạn" if d < 0 else f" · còn {d} ngày")
        st.markdown(f"**{m['ten']}** — {m['tc']} tín chỉ · mục tiêu {m['mt']}{tag}")
        c1, c2 = st.columns([5, 1])
        new = c1.slider("Tiến độ (%)", 0, 100, int(m["pct"]), 5, key=f"p{m['id']}")
        if new != m["pct"]:
            run("UPDATE mon_hoc SET pct=? WHERE id=?", (new, m["id"]))
        if c2.button("Xóa", key=f"x{m['id']}"):
            run("DELETE FROM mon_hoc WHERE id=?", (m["id"],))
            st.rerun()
    rows = query("SELECT tc, pct FROM mon_hoc WHERE mssv=?", (mssv,))
    tot = sum(r["tc"] for r in rows) or 1
    p = round(sum(r["pct"] * r["tc"] for r in rows) / tot)
    with overall:
        st.metric("Tiến độ tổng thể", f"{p}%")
        st.progress(p / 100)


def advice_tab(mssv):
    gio = st.number_input("Số giờ có thể học mỗi ngày", 0.5, 12.0, 3.0, 0.5)
    rows = query("SELECT * FROM mon_hoc WHERE mssv=? AND pct<100", (mssv,))
    if not rows:
        st.info("Chưa có môn đang học dở. Hãy thêm môn ở tab Tiến độ.")
        return
    items = []
    for m in rows:
        d = days_left(m["han"])
        urg = 1 if d is None else 3 if d <= 7 else 2 if d <= 21 else 1
        w = (100 - m["pct"]) / 100 * urg * (0.6 + m["mt"] / 10) * math.sqrt(m["tc"])
        items.append((w, d, m))
    items.sort(key=lambda x: -x[0])
    tong = sum(x[0] for x in items)
    st.write(f"Với **{gio} giờ/ngày**, thứ tự ưu tiên và thời gian nên dành:")
    for i, (w, d, m) in enumerate(items, 1):
        g = max(0.25, round(gio * w / tong * 4) / 4)
        why = []
        if d is not None and d < 0: why.append("đã quá hạn, xử lý ngay")
        elif d is not None and d <= 7: why.append(f"còn {d} ngày, rất gấp")
        elif d is not None and d <= 21: why.append(f"còn {d} ngày")
        if m["pct"] < 30: why.append(f"mới hoàn thành {m['pct']}%")
        if m["mt"] >= 8.5: why.append(f"mục tiêu cao ({m['mt']})")
        st.markdown(f"{i}. **{m['ten']}**: {g} giờ/ngày" + (f" _({', '.join(why)})_" if why else ""))
    st.caption("Mẹo: học theo phiên 25–45 phút, nghỉ 5–10 phút, cập nhật tiến độ cuối ngày.")


# ---------------------------------------------------------------- Khảo sát điểm số
def survey_screen():
    st.title("📝 Khảo sát điểm số")
    st.write("Vui lòng điền thông tin bên dưới.")
    with st.form("f_khao_sat", clear_on_submit=True):
        ten = st.text_input("Họ và tên")
        mssv = st.text_input("MSSV (không bắt buộc)")
        mon = st.text_input("Môn học")
        diem = st.number_input("Điểm (thang 10)", 0.0, 10.0, 0.0, 0.1)
        gui = st.form_submit_button("Gửi", type="primary")
    if gui:
        if not ten.strip() or not mon.strip():
            st.error("⚠️ Vui lòng nhập đầy đủ Họ tên và Môn học.")
        else:
            run("INSERT INTO khao_sat(thoi_gian, ten, mssv, mon, diem) VALUES (?,?,?,?,?)",
                (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), ten.strip(), mssv.strip(),
                 mon.strip(), float(diem)))
            st.success("✅ Đã ghi nhận điểm của bạn. Cảm ơn!")


def survey_results():
    st.subheader("Kết quả khảo sát điểm số")
    rows = query("SELECT thoi_gian, ten, mssv, mon, diem FROM khao_sat ORDER BY id DESC")
    if not rows:
        st.info("Chưa có phản hồi nào.")
        return
    df = pd.DataFrame([dict(r) for r in rows])
    c1, c2 = st.columns(2)
    c1.metric("Số phản hồi", len(df))
    c2.metric("Điểm trung bình chung", f"{df['diem'].mean():.2f}")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("Điểm trung bình theo môn")
    st.bar_chart(df.groupby("mon")["diem"].mean())
    st.download_button("⬇ Tải kết quả khảo sát (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                       "khao-sat.csv", "text/csv")


# ---------------------------------------------------------------- Chạy chính
if not secret("DATABASE_URL"):
    st.error("Chưa đặt DATABASE_URL trong Secrets. Xem hướng dẫn nối Supabase.")
    st.stop()
try:
    init_db()
except Exception as e:
    st.error("Không kết nối được cơ sở dữ liệu. Kiểm tra lại DATABASE_URL trong Secrets.")
    st.caption(f"Chi tiết: {type(e).__name__}")
    st.stop()

if st.query_params.get("trang") == "khao-sat":
    survey_screen()
    st.stop()

user = st.session_state.get("user")
if not user:
    login_screen()
else:
    top1, top2 = st.columns([4, 1])
    top1.title("🎓 Cổng học tập cá nhân")
    if top2.button("Đăng xuất"):
        st.session_state.pop("user")
        st.rerun()
    if user["role"] == "gv":
        teacher_screen()
        st.divider()
        survey_results()
    else:
        st.caption(f"Xin chào {user['ten']} ({user['mssv']})")
        a, b, c = st.tabs(["Điểm của tôi", "Tiến độ", "Gợi ý học tập"])
        with a: scores_tab(user["mssv"])
        with b: progress_tab(user["mssv"])
        with c: advice_tab(user["mssv"])
