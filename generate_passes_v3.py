#!/usr/bin/env python3
"""MySargal — Générateur Apple Wallet v3"""
import json, hashlib, os, zipfile, subprocess, requests
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

SUPABASE_URL = "https://iiocxlvcuoqafzlisqwd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlpb2N4bHZjdW9xYWZ6bGlzcXdkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUzNTgwODIsImV4cCI6MjA5MDkzNDA4Mn0.o-dRdHDGc5_IwCGhK5Ri67CCtZRj6J4evsxgBkMgvao"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_PATH  = os.path.join(SCRIPT_DIR, "mysargal-pass.pem")
KEY_PATH   = os.path.join(SCRIPT_DIR, "mysargal-pass.key")
WWDR_PATH  = os.path.join(SCRIPT_DIR, "AppleWWDRCAG4.pem")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "passes")
PASS_TYPE  = "pass.com.mysargal.app"
TEAM_ID    = "6779DNV7Y5"
GREEN      = (0, 190, 92)
HEADERS    = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

os.makedirs(OUTPUT_DIR, exist_ok=True)

def fmt_cfa(n):
    return f"{int(n):,} CFA".replace(",", " ")

def tier_label(t):
    return {"silver": "🥈 Silver", "gold": "🥇 Gold"}.get(t or "", "🥉 Bronze")

def supabase_get(table, params="select=*"):
    """Appel Supabase avec gestion d'erreur"""
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    data = r.json()
    # Supabase retourne une liste ou un dict d'erreur
    if isinstance(data, list):
        return data
    print(f"  ⚠️  Supabase {table}: {data}")
    return []

# ── Images ───────────────────────────────────────────────────────────
def make_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size-1, size-1], radius=size//5, fill=GREEN)
    cx, cy = size//2, size//2
    bw, bh = int(size*.50), int(size*.30)
    bx, by = cx-bw//2, cy-bh//2+int(size*.06)
    d.rectangle([bx, by, bx+bw, by+bh], fill=(255,255,255))
    lh = int(size*.11)
    d.rectangle([bx-2, by-lh, bx+bw+2, by], fill=(255,255,255))
    rw = max(int(size*.07), 2)
    d.rectangle([cx-rw//2, by-lh-2, cx+rw//2, by+bh], fill=GREEN)
    br = int(size*.08)
    d.ellipse([cx-br*2-1, by-lh-br, cx-1, by-lh+br], fill=(255,255,255))
    d.ellipse([cx+1, by-lh-br, cx+br*2+1, by-lh+br], fill=(255,255,255))
    return img

def make_logo(w, h):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    icon = make_icon(h-4).resize((h-4, h-4), Image.LANCZOS)
    img.paste(icon, (2, 2), icon)
    return img

def save_images(folder):
    for size, suffix in [(29,""),(58,"@2x"),(87,"@3x")]:
        make_icon(size).save(f"{folder}/icon{suffix}.png")
    make_logo(120, 60).save(f"{folder}/logo.png")
    make_logo(240, 120).save(f"{folder}/logo@2x.png")
    Image.new("RGB", (375, 90), GREEN).save(f"{folder}/strip.png")
    Image.new("RGB", (750, 180), GREEN).save(f"{folder}/strip@2x.png")

# ── PKPass ────────────────────────────────────────────────────────────
def build(folder, pass_json, out):
    with open(f"{folder}/pass.json", "w") as f:
        json.dump(pass_json, f, ensure_ascii=False, indent=2)
    manifest = {}
    for fn in os.listdir(folder):
        if fn in ("manifest.json", "signature"): continue
        fp = f"{folder}/{fn}"
        if os.path.isfile(fp):
            with open(fp, "rb") as f:
                manifest[fn] = hashlib.sha1(f.read()).hexdigest()
    with open(f"{folder}/manifest.json", "w") as f:
        json.dump(manifest, f)
    subprocess.run(
        ["openssl","smime","-sign","-binary",
         "-signer", CERT_PATH, "-inkey", KEY_PATH,
         "-certfile", WWDR_PATH,
         "-in", f"{folder}/manifest.json",
         "-out", f"{folder}/signature",
         "-outform","DER","-nodetach"],
        capture_output=True
    )
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(folder):
            if os.path.isfile(f"{folder}/{fn}"):
                zf.write(f"{folder}/{fn}", fn)

def gen_loyalty(card, merchant):
    code  = card["code"]
    pts   = card.get("pts", 0)
    thr   = merchant.get("reward_threshold", 100)
    mname = merchant.get("name", "MySargal")
    pct   = min(int(pts / max(thr,1) * 100), 100)
    folder = f"/tmp/msp_{code}"
    os.makedirs(folder, exist_ok=True)
    save_images(folder)
    p = {
        "formatVersion":1, "passTypeIdentifier":PASS_TYPE,
        "serialNumber":code, "teamIdentifier":TEAM_ID,
        "organizationName":"MySargal",
        "description":f"Carte de Fidélité — {mname}",
        "logoText":"",
        "backgroundColor":"rgb(240,252,235)",
        "foregroundColor":"rgb(10,10,10)",
        "labelColor":"rgb(0,150,70)",
        "storeCard":{
            "headerFields":   [{"key":"b","label":"BOUTIQUE","value":mname}],
            "primaryFields":  [{"key":"p","label":"POINTS","value":str(pts)}],
            "secondaryFields":[
                {"key":"c","label":"CLIENT","value":card.get("client_name","")},
                {"key":"t","label":"PALIER","value":f"{thr} pts"}],
            "auxiliaryFields":[
                {"key":"cd","label":"CODE","value":code},
                {"key":"nv","label":"NIVEAU","value":tier_label(card.get("tier"))}],
            "backFields":[
                {"key":"i","label":"Comment utiliser",
                 "value":"Présentez le QR code en caisse. Points ajoutés automatiquement."},
                {"key":"pg","label":"Progression","value":f"{pts}/{thr} pts ({pct}%)"},
                {"key":"nx","label":"Prochaine récompense",
                 "value":f"Plus que {max(thr-pts,0)} point(s) !"},
                {"key":"s","label":"MySargal","value":"https://mysargal.com",
                 "dataDetectorTypes":["PKDataDetectorTypeLink"]},
                {"key":"w","label":"Support","value":"+221 77 760 89 83",
                 "dataDetectorTypes":["PKDataDetectorTypePhoneNumber"]}]},
        "barcodes":[{"message":f"https://mysargal.com/c/?code={code}",
                     "format":"PKBarcodeFormatQR","messageEncoding":"iso-8859-1",
                     "altText":code}]
    }
    build(folder, p, f"{OUTPUT_DIR}/{code}.pkpass")
    print(f"  ✓ {code}.pkpass")

def gen_giftcard(gc, merchant):
    code  = gc["code"]
    bal   = gc.get("balance", 0)
    init  = gc.get("initial_amount", 0)
    exp   = gc.get("expires_at", "N/A")
    mname = merchant.get("name", "MySargal") if merchant else "MySargal"
    if exp and exp != "N/A":
        try:
            from datetime import datetime
            exp = datetime.fromisoformat(exp.replace("Z","+00:00")).strftime("%b %Y")
        except: pass
    folder = f"/tmp/msp_{code}"
    os.makedirs(folder, exist_ok=True)
    save_images(folder)
    p = {
        "formatVersion":1, "passTypeIdentifier":PASS_TYPE,
        "serialNumber":code, "teamIdentifier":TEAM_ID,
        "organizationName":"MySargal",
        "description":f"Carte Cadeau — {mname}",
        "logoText":"",
        "backgroundColor":"rgb(240,252,235)",
        "foregroundColor":"rgb(10,10,10)",
        "labelColor":"rgb(0,150,70)",
        "storeCard":{
            "headerFields":   [{"key":"b","label":"BOUTIQUE","value":mname}],
            "primaryFields":  [{"key":"s","label":"SOLDE","value":fmt_cfa(bal)}],
            "secondaryFields":[
                {"key":"r","label":"BÉNÉFICIAIRE","value":gc.get("recipient_name","")},
                {"key":"e","label":"EXPIRE","value":exp}],
            "auxiliaryFields":[
                {"key":"cd","label":"CODE","value":code},
                {"key":"in","label":"INITIAL","value":fmt_cfa(init)}],
            "backFields":[
                {"key":"i","label":"Comment utiliser",
                 "value":"Présentez le QR code en caisse. Solde déduit automatiquement."},
                {"key":"si","label":"MySargal","value":"https://mysargal.com",
                 "dataDetectorTypes":["PKDataDetectorTypeLink"]},
                {"key":"w","label":"Support","value":"+221 77 760 89 83",
                 "dataDetectorTypes":["PKDataDetectorTypePhoneNumber"]}]},
        "barcodes":[{"message":f"https://mysargal.com/c/?code={code}",
                     "format":"PKBarcodeFormatQR","messageEncoding":"iso-8859-1",
                     "altText":code}]
    }
    build(folder, p, f"{OUTPUT_DIR}/{code}.pkpass")
    print(f"  ✓ {code}.pkpass")

def main():
    print("🍎 MySargal — Génération Apple Wallet")
    print("=" * 42)
    for path, label in [(CERT_PATH,"Certificat"),(KEY_PATH,"Clé privée"),(WWDR_PATH,"Cert Apple WWDR")]:
        if not os.path.exists(path):
            print(f"❌ {label} manquant : {path}"); return
    print("✓ Certificats OK\n")

    merchants = {m["id"]: m for m in supabase_get("merchants","select=id,name,reward_threshold")}
    print(f"📦 {len(merchants)} marchand(s)")

    print("\n🎴 Cartes de fidélité...")
    for card in supabase_get("loyalty_cards"):
        m = merchants.get(card.get("merchant_id"), {"name":"MySargal","reward_threshold":100})
        try:   gen_loyalty(card, m)
        except Exception as e: print(f"  ✗ {card.get('code','?')}: {e}")

    print("\n🎁 Cartes cadeaux...")
    for gc in supabase_get("gift_cards"):
        m = merchants.get(gc.get("merchant_id"), {"name":"MySargal"})
        try:   gen_giftcard(gc, m)
        except Exception as e: print(f"  ✗ {gc.get('code','?')}: {e}")

    total = len(list(Path(OUTPUT_DIR).glob("*.pkpass")))
    print(f"\n✅ {total} passes générés dans ./passes/")
    print("📤 Glisse le dossier passes/ sur Cloudflare avec ton site")

if __name__ == "__main__":
    main()
