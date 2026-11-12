<div align="center">

<img src="docs/logo.svg" width="96" alt="Vizavi Studio logo">

# Vizavi Studio

**Turn a voice recording into a finished video – together with Claude.**
You record your voice, Claude designs the video, your own PC renders it.

[![Download for Windows](https://img.shields.io/badge/Download-for%20Windows-0A84FF?style=for-the-badge&logo=windows11&logoColor=white)](https://github.com/diyorvekdrs/vizavi-studio/releases/latest/download/Vizavi-Studio-Installer.cmd)
&nbsp;
[![Download zip](https://img.shields.io/badge/or-download%20the%20zip-555?style=for-the-badge)](https://github.com/diyorvekdrs/vizavi-studio/releases/latest/download/Vizavi-Studio-Setup.zip)

<sub>Or paste one line into PowerShell – see <a href="#install">Install</a></sub>

![Latest version](https://img.shields.io/github/v/release/diyorvekdrs/vizavi-studio?label=version&color=FF9F0A)
![Windows 10 and 11](https://img.shields.io/badge/Windows-10%20%7C%2011-555)
![Free, non-commercial](https://img.shields.io/badge/free-personal%20use-30D158)

<img src="docs/screenshot-project.jpg" alt="Vizavi Studio: a project waiting for review, with the preview, automatic checks and transcript" width="900">

</div>

---

## What it does

Drop a voice recording on the window, say what you want, and Vizavi Studio prepares everything Claude needs
to design your video: word-by-word timing, captions, music beats, your pictures and clips. Claude sends back
the video as code, and your PC renders it – a preview first, then the final in any size you like.

- 🎙️ **Narrated explainers, Shorts, Reels, TikToks, promos, kinetic typography, logo stings** – any size and frame rate
- 🇺🇿 **Excellent Uzbek speech recognition** – exact spelling from your script, timing from your voice
- 🖥️ **Renders on your own PC** – uses an NVIDIA graphics card when you have one, the processor when you don't
- 🎞️ **Your footage stays full quality** – Claude works with small copies, the render uses your originals
- 🎨 **Save a look you like as a style** and get your next videos in the same style
- 🔎 **Automatic checks on every preview** – text cut off or under the TikTok/Reels buttons, too small, too faint,
  too brief to read, misspelled; sound and picture problems – ranked from *broken* to *polish*
- ♻️ **Only what changed is rendered again** – after your notes, unchanged seconds are reused
- 🔄 **Updates itself** – one click when a new version is out

## How it works

```mermaid
flowchart LR
    A["🎙️ You<br/>drop a voice recording"] --> B["📦 Vizavi Studio<br/>prepares a package"]
    B --> C["🤖 Claude<br/>designs the video"]
    C --> D["🎬 Vizavi Studio<br/>renders a preview"]
    D -->|"changes?<br/>send notes"| C
    D -->|"looks good"| E["✅ Final video<br/>in every size"]
```

You only move zip files between the app and a Claude chat – the app copies the message for you and picks up
Claude's answer from your Downloads folder by itself.

---

## What you need

| | |
|---|---|
| 💻 **Computer** | Windows 10 (1809 or newer) or Windows 11, 64-bit |
| 💾 **Disk space** | about 15 GB free – on any drive, you choose during install |
| 🌐 **Internet** | for the first start – it downloads 2–8 GB of components, depending on your PC |
| 🤖 **Claude** | a [claude.ai](https://claude.ai) account |
| 🎮 **Graphics card** | *not required.* An NVIDIA card makes renders much faster |

## Install

> ⏱️ About 5–30 minutes, mostly waiting. You do this **once** – after that the app updates itself.
> Pick **one** of the three ways – they all install the same thing.

### ⭐ Way 1 – Quick installer (easiest)

1. Download **[Vizavi-Studio-Installer.cmd](https://github.com/diyorvekdrs/vizavi-studio/releases/latest/download/Vizavi-Studio-Installer.cmd)** – one tiny file.
2. Double-click it. It downloads the newest version, checks it and installs it. Nothing to unzip.

> [!TIP]
> Your browser may say the file *"isn't commonly downloaded"* – choose **Keep** (in Edge: **⋯ → Keep → Keep anyway**).
> When Windows says **"Windows protected your PC"**, click **More info → Run anyway**.
> The app isn't signed by a company, so Windows warns about it the first time.

### ⚡ Way 2 – One line in PowerShell

1. Press **Win + X** and choose **Terminal** (or **Windows PowerShell**).
2. Paste this line and press **Enter**:

```powershell
irm https://raw.githubusercontent.com/diyorvekdrs/vizavi-studio/main/get.ps1 | iex
```

It does exactly what the quick installer does – you can [read the script](get.ps1) first.

### 📦 Way 3 – The zip (classic)

1. Download **[Vizavi-Studio-Setup.zip](https://github.com/diyorvekdrs/vizavi-studio/releases/latest/download/Vizavi-Studio-Setup.zip)**.
2. Right-click it → **Extract All…** → **Extract**.
3. Open the extracted folder and double-click **`Install Vizavi Studio`**.

### Choose where it goes

The installer asks where to put Vizavi Studio. Press **Enter** for the normal place on drive **C:**, or
type another drive letter (for example **D**) or a folder – useful when C: is almost full. In another folder,
*everything* big goes there: the program, the speech models (3–8 GB), the download caches and your projects.

> [!TIP]
> Already installed on C: and running out of space? Run the installer again (any of the three ways) and type the
> other drive. It moves the program, the installed components and the speech models there – nothing is
> downloaded twice – and offers to move your projects and delete the old copy.

### Then: let it get ready

The app opens and shows *Getting Vizavi Studio ready*. It looks at your PC and installs only what your
computer can use. Keep the window open until the bottom bar says **Ready**. Later starts are instant.

> [!NOTE]
> If it asks to install the **Microsoft Visual C++ runtime**, click **Yes**.
> Already have an older Vizavi Studio? Just install over it – your projects and settings stay.

## Open the app

- 🖱️ Double-click **Vizavi Studio** on your **Desktop**, or
- 🔎 press the **Windows key**, type **Vizavi** and press **Enter**, or
- 🎙️ right-click any voice recording → **Send to → Vizavi Studio** – the app opens with it, ready for a new project.

Tip: right-click the app in the taskbar → **Pin to taskbar** to keep it one click away.

---

## Make your first video

1. **Drop your voice recording** (wav, mp3, m4a…) on the window. Add music, pictures, clips or your script
   if you have them.
2. **Fill in *What I want*** – the story, the mood, must-show moments. Use *Take care of* for things
   that must or must not happen.
3. Pick a **preset** (YouTube, Shorts, Instagram…) and click **Create package for Claude**.
4. Click **Copy message**, open a **new chat** on [claude.ai](https://claude.ai), drag the zip into the chat,
   paste the message (**Ctrl + V**) and send.
5. When Claude replies with a zip, **just download it** – the app finds it and renders a preview.
6. **Watch the preview.**
   - Happy? → **Approve and render final**.
   - Want changes? → write notes, then drag the review zip into the **same** Claude chat with the copied message.
7. Your video is in the project's **output** folder (**Open folder**).

<p align="center"><img src="docs/screenshot-new-project.jpg" alt="The New project window: preset, narration, music and what you want" width="760"></p>

> [!NOTE]
> The very first transcription downloads the speech models once (a few GB), so it takes longer than the next ones.

## Updates

When a new version is out, the app shows **"Vizavi Studio X is available"** at the top.

**What's new** tells you what changed · **Update now** installs it in about a minute – the window reconnects
by itself · **Later** hides it until the next version.

Your projects, settings and installed components are never touched. If something seems wrong after an update:
**Settings → Updates → Undo last update**.

## Good to know

- 🎨 **Save as style** – liked how a video turned out? Press **Save as style…** on its page. In a new project,
  choose it under **Look → Match a saved style** and Claude makes the new video in the same look.
- ⚡ **Final size** – a 2K or 4K final takes longer. Pick a smaller *Final size* on the preview card when you
  need it fast.
- 🧾 **My rules** (Settings) – rules added to every project, e.g. *"on-screen text in Uzbek Latin only"*.
  A note you'll want every time? **Save as a rule…** under the notes box.
- 🎯 **Viewers should believe…** (New project) – one plain sentence the video must get across. Claude builds every
  scene around it and judges the preview by it.
- 🏷️ **Automatic checks** – *Broken* and *Serious* findings are fixed by Claude first; the app asks before you
  approve a final that still has them. The quick buttons above the notes (*Bolder, Faster, Shorter…*) add one clear
  change per line.
- 🗑️ **Recently deleted** (Settings) – deleted projects and styles can be restored for 30 days. A small backup of your
  styles and project texts is made every day (**Settings → Open backups**).
- 📁 Your videos are saved in **Videos → Vizavi Studio** (change it in Settings).

## Something went wrong?

<details>
<summary><b>The app says a component is missing, or something didn't install</b></summary>

Open **Settings → Check and repair components** and keep the window open until it says it's done. The log
(bottom right of the window) shows what happened. Do the same after you install a new NVIDIA driver.
</details>

<details>
<summary><b>Double-clicking does nothing</b></summary>

Open the app folder (`%LOCALAPPDATA%\VizaviStudio`) and run **`Start Vizavi Studio (if double-click does nothing).bat`**.
If it shows an error, send it to the person who shared the app with you.
</details>

<details>
<summary><b>Drive C: is full</b></summary>

Run the installer again and type another drive letter when it asks where to install – see
[Choose where it goes](#choose-where-it-goes). **Settings → This PC** shows where the program, the speech models
and your projects are, and how much space is left on each drive.
</details>

<details>
<summary><b>Renders are slow</b></summary>

**Settings → This PC** shows whether the app renders on your graphics card or the processor. Without an NVIDIA
card everything runs on the processor – it works, just slower. Choosing a smaller **Final size** helps a lot.
</details>

<details>
<summary><b>Claude's zip isn't picked up</b></summary>

Make sure *Pick up Claude's zips from Downloads* is on in **Settings**, and that the zip went to the Downloads folder
shown there. You can always drag the zip onto the app window yourself.
</details>

<details>
<summary><b>I deleted a project or a style by mistake</b></summary>

**Settings → Recently deleted → Restore.** Everything stays there for 30 days. Older than that: **Settings → Open
backups** has a daily zip with your styles, project settings, transcripts and Claude's code (not the recordings).
</details>

<details>
<summary><b>An update didn't work</b></summary>

The app goes back to the previous version by itself if a new one doesn't start. You can also use
**Settings → Updates → Undo last update**. Details are in `%LOCALAPPDATA%\VizaviStudio\.update\update.log`.
</details>

## Uninstall

**Windows Settings → Apps → Vizavi Studio → Uninstall.** Your videos stay where they are.

## Privacy

Everything runs on your own PC. The app talks to Claude only through the zips **you** drag into a chat, and it
asks GitHub whether a new version exists (turn that off in **Settings → Updates**). Nothing else leaves your computer.

---

<details>
<summary><b>For the maintainer – publishing a new version</b></summary>

1. Change the code in `app\`.
2. Double-click **`Publish update.cmd`** and type one line about what's new.

The script raises the version, commits, tags, pushes and publishes a GitHub release with a checksum. Every
installed app offers the update within a few hours (or right away with **Settings → Check now**).
Needs [git](https://git-scm.com) and the [GitHub CLI](https://cli.github.com) (`gh auth login`).
A dry run that only lists what would be published: `py -3 app\setup\publish_update.py --dry`.

Tests: `py -3 tests\run_all.py` (add `npm install` in `tests\` once for the UI test). They run on GitHub for every
push (Actions → Tests) on Windows; publish only when they're green.

Only what `.gitignore` allows is ever published – settings, projects, models, the Python environment and your
own project library stay on your PC. More detail about features and folders: [`app/README.md`](app/README.md).
</details>

<div align="center">
<sub>Free for personal, non-commercial use. Precise word timing uses Meta's MMS model (CC BY-NC 4.0); it can be
turned off in Settings.</sub>
</div>
