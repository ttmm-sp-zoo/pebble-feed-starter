# pebble-feed-starter

Host your own **Pebble appstore feed** — a source you (and your users) can add inside the Pebble mobile app, serving your own watchfaces and apps.

Pebble's mobile app can read from multiple appstore "feeds" (like APT/AUR for packages). This is a minimal, self-hostable reference implementation of that feed format — the same API documented at [appstore-api.repebble.com](https://appstore-api.repebble.com/). Drop your `.pbw` builds and some images into folders, run one script, upload the result to any PHP host. No database, no framework.

Built and contributed by [TTMM](https://ttmm.is) in the spirit of Pebble's open-source revival. The TTMM feed at [apps.ttmm.is](https://apps.ttmm.is) runs on this design in production; this repository is the generic version of it, with two placeholder apps in place of real content.

---

## What you get

- **Static feed + one tiny PHP router.** Cards, collections, per-platform descriptions and screenshots, an onboarding/home endpoint, and a bulk endpoint for update checks.
- **Per-platform content.** Different description and screenshots for aplite / basalt / chalk / diorite / emery / gabbro from one folder per app.
- **Works on cheap shared hosting.** PHP 7.4+ and an `.htaccess` rewrite. That's it.

## How it works

```
content/<your-app>/          you edit this
  manifest.yaml              title, version, compatibility, collections…
  descriptions/default.txt   (+ optional basalt.txt, chalk.txt … per platform)
  images/<platform>/*.png     screenshots (144×168, chalk 180×180, emery 200×228, gabbro 260×260)
  images/icon.png            square icon  (featured.png / banner.png optional)
  app/<your-app>.pbw         your compiled watchface/app

generate.py  →  public/      upload this whole folder to your host
```

`public/` contains `index.php`, `.htaccess`, `data/` (the JSON feed), `assets/` (images) and `pbw/` (binaries). The router serves the documented endpoints; everything else is plain files.

## Quick start

```bash
pip install pyyaml pillow
# 1. edit config.yaml  → set base_url to where you'll host the feed
# 2. replace content/demo-* with your own app folder(s)
python3 generate.py
# 3. upload the CONTENTS of public/ to that location (keep the hidden .htaccess!)
```

Your feed URL is whatever you set as `base_url` (e.g. `https://apps.example.com/feed`).

## Verifying

Open in a browser:

- `…/api/v1/apps/dev/x` — your whole catalog
- `…/api/v1/apps/id/<id>?hardware=chalk` — one card; note the description/screenshots switch per `hardware`
- `…/api/v1/home/watchfaces` — the feed's home payload

The `?hardware=` parameter is how the app asks for a specific watch; the router answers with that platform's description and screenshots.

### A live instance

Exactly this repository — the two placeholder apps, nothing else — runs on ordinary shared
hosting at `https://apps.ttmm.is/feed-demo`:

- <https://apps.ttmm.is/feed-demo/data/index.json> — the generated feed, served as plain files
- <https://apps.ttmm.is/feed-demo/api/v1/apps/dev/x> — the same catalog through the router
- <https://apps.ttmm.is/feed-demo/api/v1/apps/id/8520230fd395f134fabfa368?hardware=aplite> —
  one card; change `aplite` to `basalt` and the description changes with it

Add it as a source if you want to see how a feed looks inside the Pebble app. Install will fail
there — the demo `.pbw` files are placeholders (see Notes).

## Installing today

Two ways, and both work now.

**As a source.** Open your feed's address on the phone and follow a
`pebble://add-store-feed/<name>/<url-encoded feed url>` link, or add it by hand in the Pebble
app under **Appstore Sources → Add Source**. Whatever your apps publish then appears under
**Apps → \<name\>**.

**As a file.** A direct link to a `.pbw` (`…/pbw/<name>.pbw`) hands the binary to the Pebble
app for sideloading. No source needed — useful for a one-off, or before someone has added you.

### Three things that cost me time

- **The source address must match, character for character**, what you set as `base_url` and
  what the feed actually serves. A trailing slash or a missing `https://` subscribes to nothing,
  silently.
- **The app can hold a stale copy of a feed.** If your changes do not show up, reinstalling the
  phone app forces a fresh sync.
- **Keep the hidden `.htaccess`.** Uploading `public/` without it breaks the rewrite, and on some
  hosts uploading into the wrong directory overwrites an `.htaccess` you meant to keep.

## Notes

- The included `demo-one` / `demo-two` `.pbw` files are **placeholders** so the generator runs end-to-end. Replace them with real builds.
- Set `configurable: true` in a manifest **only if the app really has a settings page**. The feed advertises it (`capabilities` and `latest_release.settings_page_state`), and the phone app offers a settings screen on that basis — claiming one you do not have gives your users a dead button.
- IDs are derived stably from each folder name. Keep folder names stable to keep IDs (and any deep links) stable.
- This is a community starter kit, provided as-is. It implements the public feed format; it is not affiliated with or endorsed by Core Devices.

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, ship your own store.
