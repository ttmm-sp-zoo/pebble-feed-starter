#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pebble-feed-starter — build a self-hosted Pebble appstore feed from simple folders.

Usage:
    python3 generate.py

Reads:  config.yaml  +  content/<app>/manifest.yaml (+ descriptions/, images/, app/*.pbw)
Writes: public/      (upload its whole contents to your feed directory)

The output speaks the Pebble Appstore API format documented at
https://appstore-api.repebble.com/ — so the Pebble mobile app can read it as a source.

Requires: Python 3.8+, pyyaml, pillow   (pip install pyyaml pillow)
License: MIT
"""
import os, sys, json, re, shutil, hashlib, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(HERE, "content")
PUB = os.path.join(HERE, "public")

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency. Run: pip install pyyaml pillow")

# screenshot pixel size the app expects, per hardware platform
DIMS = {"aplite": (144, 168), "basalt": (144, 168), "diorite": (144, 168),
        "flint": (144, 168), "emery": (200, 228), "chalk": (180, 180), "gabbro": (260, 260)}
ALL_PLATFORMS = ["aplite", "basalt", "chalk", "diorite", "emery", "flint", "gabbro"]


def load_config():
    f = os.path.join(HERE, "config.yaml")
    cfg = yaml.safe_load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
    cfg.setdefault("base_url", "https://example.com/feed")
    cfg.setdefault("developer", {"id": gen_id("developer"), "name": "Your Name"})
    cfg.setdefault("category", {"id": gen_id("faces"), "name": "Faces", "slug": "faces", "color": "ffffff"})
    cfg.setdefault("max_screenshots", 5)
    cfg["base_path"] = "/" + cfg["base_url"].split("://", 1)[-1].split("/", 1)[1].strip("/") if "/" in cfg["base_url"].split("://", 1)[-1] else ""
    return cfg


def gen_id(seed):
    return hashlib.md5(seed.encode()).hexdigest()[:24]


def natsort(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def read_desc(d, plat):
    base = os.path.join(d, "descriptions")
    for name in (f"{plat}.txt", "default.txt"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return open(p, encoding="utf-8").read().strip()
    return ""


def build():
    cfg = load_config()
    BASE = cfg["base_url"].rstrip("/")
    if os.path.isdir(PUB):
        shutil.rmtree(PUB)
    for sub in ("data/apps", "assets", "pbw"):
        os.makedirs(os.path.join(PUB, sub), exist_ok=True)

    from PIL import Image
    apps, collections = [], {}
    today = datetime.date.today().isoformat() + "T00:00:00"

    for name in sorted(os.listdir(CONTENT)):
        d = os.path.join(CONTENT, name)
        mf = os.path.join(d, "manifest.yaml")
        if not os.path.isdir(d) or not os.path.exists(mf):
            continue
        m = yaml.safe_load(open(mf, encoding="utf-8"))
        app_id = gen_id(name)
        targets = [p for p in ALL_PLATFORMS if p in (m.get("compatibility") or [])]
        adir = os.path.join(PUB, "assets", app_id)

        # screenshots per platform
        screens = {}
        for plat in targets:
            src = os.path.join(d, "images", plat)
            if not os.path.isdir(src):
                continue
            files = sorted([f for f in os.listdir(src) if f.lower().endswith((".png", ".gif"))], key=natsort)[:cfg["max_screenshots"]]
            urls = []
            os.makedirs(os.path.join(adir, "screenshots", plat), exist_ok=True)
            for i, f in enumerate(files):
                ext = os.path.splitext(f)[1].lower()
                dst = f"screenshots/{plat}/screenshot-{i}{ext}"
                shutil.copy2(os.path.join(src, f), os.path.join(adir, dst))
                urls.append(f"{BASE}/assets/{app_id}/{dst}")
            screens[plat] = urls

        # icon / list image (square) + optional featured + optional banner
        list_img, featured_url, banner_url = {}, None, None
        os.makedirs(os.path.join(adir, "icons"), exist_ok=True)
        icon = os.path.join(d, "images", "icon.png")
        featured = os.path.join(d, "images", "featured.png")
        banner = os.path.join(d, "images", "banner.png")
        squaresrc = featured if os.path.exists(featured) else (icon if os.path.exists(icon) else None)
        if os.path.exists(featured):
            shutil.copy2(featured, os.path.join(adir, "icons", "featured.png"))
            featured_url = f"{BASE}/assets/{app_id}/icons/featured.png"
        if squaresrc:
            im0 = Image.open(squaresrc).convert("RGB")
            for size, key in ((144, "144x144"), (80, "80x80")):
                s = min(im0.width, im0.height)
                im = im0.crop(((im0.width - s) // 2, (im0.height - s) // 2, (im0.width + s) // 2, (im0.height + s) // 2)).resize((size, size), Image.LANCZOS)
                im.save(os.path.join(adir, "icons", f"list-{size}.png"))
                list_img[key] = f"{BASE}/assets/{app_id}/icons/list-{size}.png"
        if os.path.exists(banner):
            shutil.copy2(banner, os.path.join(adir, "icons", "banner.png"))
            banner_url = f"{BASE}/assets/{app_id}/icons/banner.png"

        # binary
        appdir = os.path.join(d, "app")
        pbw = next((f for f in sorted(os.listdir(appdir)) if f.endswith(".pbw")), None) if os.path.isdir(appdir) else None
        version = str(m.get("version", "1.0"))
        pbw_url = None
        if pbw:
            dst = f"{name}-v{version}.pbw"
            shutil.copy2(os.path.join(appdir, pbw), os.path.join(PUB, "pbw", dst))
            pbw_url = f"{BASE}/pbw/{dst}"

        # descriptions
        descs = {p: read_desc(d, p) for p in targets}
        footer = (m.get("footer") or "").strip()
        # Only claim a settings page if the app really has one. Allowed states in the
        # Pebble appstore API: no_page | page_loads | page_doesnt_load
        configurable = bool(m.get("configurable", False))
        def full(plat):
            body = descs.get(plat) or next((v for v in descs.values() if v), m.get("title", name))
            return (body + ("\n\n" + footer if footer else "")).strip()
        default_desc = full(targets[0]) if targets else (m.get("title", name))

        compat = {p: {"supported": p in targets, "firmware": {"major": 3}} for p in ALL_PLATFORMS}
        compat["android"] = {"supported": True}
        compat["ios"] = {"supported": True, "min_js_version": 1}

        app = {
            "author": cfg["developer"]["name"],
            "capabilities": (["configurable"] if configurable else []),
            "category": cfg["category"]["name"], "category_id": cfg["category"]["id"], "category_color": cfg["category"]["color"],
            "changelog": [{"version": version, "published_date": today, "release_notes": m.get("release_notes") or ""}],
            "companions": {"android": None, "ios": None},
            "compatibility": compat,
            "created_at": today,
            "description": default_desc,
            "developer_id": cfg["developer"]["id"],
            "developer_claimed": True, "contactable": True,
            "header_images": ([{"720x320": banner_url, "orig": banner_url}] if banner_url else []),
            "hearts": int(m.get("hearts", 0)),
            "icon_image": {"28x28": "", "48x48": ""},
            "id": app_id,
            "latest_release": {
                "id": gen_id(app_id + version), "js_md5": None, "js_version": -1,
                "pbw_file": pbw_url, "published_date": today,
                "release_notes": m.get("release_notes") or "",
                "settings_page_state": ("page_loads" if configurable else "no_page"),
                "companion_android_state": "no_companion", "companion_ios_state": "no_companion",
                "version": version,
            },
            "links": {"share": m.get("website", "")},
            "list_image": list_img,
            "featured_image": featured_url,
            "published_date": today,
            "screenshot_hardware": "basalt" if "basalt" in targets else (targets[0] if targets else "basalt"),
            "screenshot_images": [{"144x168": u} for u in screens.get("basalt", [])[:1]],
            "source": None,
            "title": m.get("title", name),
            "type": m.get("type", "watchface"),
            "uuid": str(__import__("uuid").uuid5(__import__("uuid").NAMESPACE_URL, BASE + "/" + name)),
            "visible": True,
            "website": m.get("website", ""),
            "hardware_platforms": [{
                "sdk_version": "5.86", "pebble_process_info_flags": 0, "name": p,
                "description": full(p),
                "images": {"icon": list_img.get("80x80", ""), "list": list_img.get("144x144", ""),
                           "screenshot": (screens.get(p) or [""])[0]},
            } for p in targets],
            # private fields consumed by the router, stripped before output:
            "_descs": {p: full(p) for p in targets},
            "_screens": screens, "_targets": targets,
        }
        json.dump(app, open(os.path.join(PUB, "data", "apps", f"{app_id}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        apps.append({"id": app_id, "title": app["title"], "subtitle": m.get("subtitle", ""),
                     "hearts": app["hearts"], "targets": targets,
                     "featured_image": featured_url, "list_image": list_img.get("144x144"),
                     "collections": [c.lower() for c in (m.get("collections") or [])]})
        for c in (m.get("collections") or []):
            collections.setdefault(c.lower(), {"slug": c.lower(), "name": c, "application_ids": []})["application_ids"].append(app_id)

    if "all" not in collections:
        collections["all"] = {"slug": "all", "name": "All", "application_ids": [a["id"] for a in apps]}

    index = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "base_url": BASE, "base_path": cfg["base_path"],
        "developer": cfg["developer"], "category": cfg["category"],
        "apps": apps, "collections": list(collections.values()),
        "onboarding": {p: [a["id"] for a in apps if p in a["targets"]][:6] for p in ALL_PLATFORMS},
    }
    json.dump(index, open(os.path.join(PUB, "data", "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    for f in ("index.php", ".htaccess"):
        s = os.path.join(HERE, "server", f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(PUB, f))
    print(f"Built {len(apps)} app(s) into {PUB}")
    print(f"Feed base URL: {BASE}")


if __name__ == "__main__":
    build()
