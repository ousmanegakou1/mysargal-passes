#!/usr/bin/env python3
"""MySargal — Générateur Apple Wallet v5"""
import json, hashlib, os, zipfile, requests, subprocess, tempfile
from PIL import Image, ImageDraw
from pathlib import Path

SUPABASE_URL = "https://iiocxlvcuoqafzlisqwd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlpb2N4bHZjdW9xYWZ6bGlzcXdkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTM1ODA4MiwiZXhwIjoyMDkwOTM0MDgyfQ.sdZ2K4iAUOo2bfXTMgehViGC-R8H0-56EBAZ661UXL0"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_PATH  = os.path.join(SCRIPT_DIR, "mysargal-pass.pem")
KEY_PATH   = os.path.join(SCRIPT_DIR, "mysargal-pass.key")
WWDR_PATH  = os.path.join(SCRIPT_DIR, "AppleWWDRCAG4.pem")
P12_PATH   = os.path.join(SCRIPT_DIR, "mysargal-pass.p12")
P12_PASS   = "mysargal123" 
LOGO_PATH  = os.path.join(SCRIPT_DIR, "logo.png")
LOGO2X_PATH = os.path.join(SCRIPT_DIR, "logo@2x.png")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "passes")
PASS_TYPE  = "pass.com.mysargal.app"
TEAM_ID    = "6779DNV7Y5"
GREEN      = (0, 190, 92)
OPENSSL    = "/opt/homebrew/opt/openssl@3/bin/openssl"
HEADERS    = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

os.makedirs(OUTPUT_DIR, exist_ok=True)

def fmt_cfa(n):
    return f"{int(n):,} CFA".replace(",", " ")

def supabase_get(table, params="select=*"):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=HEADERS, timeout=15)
    data = r.json()
    return data if isinstance(data, list) else []

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

def save_images(folder):
    for size, suffix in [(29,""),(58,"@2x"),(87,"@3x")]:
        make_icon(size).save(f"{folder}/icon{suffix}.png")
    # Utiliser le vrai logo MySargal si disponible
    import shutil
    if os.path.exists(LOGO_PATH):
        shutil.copy(LOGO_PATH, f"{folder}/logo.png")
    else:
        make_icon(60).save(f"{folder}/logo.png")
    if os.path.exists(LOGO2X_PATH):
        shutil.copy(LOGO2X_PATH, f"{folder}/logo@2x.png")
    else:
        make_icon(120).save(f"{folder}/logo@2x.png")
    Image.new("RGB", (375, 90), GREEN).save(f"{folder}/strip.png")
    Image.new("RGB", (750, 180), GREEN).save(f"{folder}/strip@2x.png")

def sign_manifest(folder):
    """Signe le manifest avec pass-cert-only.pem + mysargal-pass.key + WWDR"""
    manifest_path = f"{folder}/manifest.json"
    signature_path = f"{folder}/signature"
    
    cert_path = os.path.join(SCRIPT_DIR, "pass-cert-only.pem")
    
    result = subprocess.run([
        OPENSSL, "smime", "-sign", "-binary",
        "-signer", cert_path,
        "-inkey", KEY_PATH,
        "-certfile", WWDR_PATH,
        "-in", manifest_path,
        "-out", signature_path,
        "-outform", "DER"
    ], capture_output=True)
    
    if result.returncode != 0:
        print(f"    ⚠️ Sign error: {result.stderr.decode()[:200]}")
    return result.returncode == 0

def build(folder, pass_json, out):
    with open(f"{folder}/pass.json", "w") as f:
        json.dump(pass_json, f, ensure_ascii=False, indent=2)
    
    # Manifest — hash de tous les fichiers sauf manifest et signature
    manifest = {}
    for fn in sorted(os.listdir(folder)):
        if fn in ("manifest.json", "signature"): continue
        fp = f"{folder}/{fn}"
        if os.path.isfile(fp):
            with open(fp, "rb") as f:
                manifest[fn] = hashlib.sha1(f.read()).hexdigest()
    
    with open(f"{folder}/manifest.json", "w") as f:
        json.dump(manifest, f)
    
    # Signature
    ok = sign_manifest(folder)
    if not ok:
        print(f"    ⚠️ Signature échouée")
    
    # ZIP
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in os.listdir(folder):
            if os.path.isfile(f"{folder}/{fn}"):
                zf.write(f"{folder}/{fn}", fn)

def gen_loyalty(card, merchant):
    code  = card["code"]
    pts   = card.get("pts", 0)
    thr   = merchant.get("threshold", 100)
    mname = merchant.get("name", "MySargal")
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
                {"key":"cd","label":"CODE","value":code}],
            "backFields":[
                {"key":"i","label":"Comment utiliser",
                 "value":"Présentez le QR code en caisse."},
                {"key":"s","label":"MySargal","value":"https://mysargal.com",
                 "dataDetectorTypes":["PKDataDetectorTypeLink"]}]},
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
                 "value":"Présentez le QR code en caisse."},
                {"key":"s","label":"MySargal","value":"https://mysargal.com",
                 "dataDetectorTypes":["PKDataDetectorTypeLink"]}]},
        "barcodes":[{"message":f"https://mysargal.com/c/?code={code}",
                     "format":"PKBarcodeFormatQR","messageEncoding":"iso-8859-1",
                     "altText":code}]
    }
    build(folder, p, f"{OUTPUT_DIR}/{code}.pkpass")
    print(f"  ✓ {code}.pkpass")

def main():
    print("🍎 MySargal — Génération Apple Wallet v5")
    print("=" * 42)
    for path, label in [(P12_PATH,"Certificat p12"),(WWDR_PATH,"Cert WWDR")]:
        if not os.path.exists(path):
            print(f"❌ {label} manquant : {path}"); return
        else:
            print(f"✓ {label} OK")
    
    # Vérifier OpenSSL Homebrew
    r = subprocess.run([OPENSSL, "version"], capture_output=True)
    print(f"✓ {r.stdout.decode().strip()}")
    print()

    merchants = {m["id"]: m for m in supabase_get("merchants","select=id,name,threshold")}
    print(f"📦 {len(merchants)} marchand(s)")

    print("\n🎴 Cartes de fidélité...")
    for card in supabase_get("loyalty_cards"):
        m = merchants.get(card.get("merchant_id"), {"name":"MySargal","reward_threshold":100})
        try: gen_loyalty(card, m)
        except Exception as e: print(f"  ✗ {card.get('code','?')}: {e}")

    print("\n🎁 Cartes cadeaux...")
    for gc in supabase_get("gift_cards"):
        m = merchants.get(gc.get("merchant_id"), {"name":"MySargal"})
        try: gen_giftcard(gc, m)
        except Exception as e: print(f"  ✗ {gc.get('code','?')}: {e}")

    total = len(list(Path(OUTPUT_DIR).glob("*.pkpass")))
    print(f"\n✅ {total} passes générés dans ./passes/")

if __name__ == "__main__":
    main()
