# 🚀 High-Performance Contact Scraper

A professional-grade, asynchronous Python tool designed to extract **Emails** and **Social Media Handles** from websites at high speed.

## ✨ Features

- **⚡ Blazing Fast**: Processes hundreds of sites per minute using asynchronous I/O (`asyncio` + `aiohttp`).
- **📧 Smart Detection**: Extracts emails and social profiles (LinkedIn, Twitter, Facebook, Instagram, YouTube).
- **🕸️ Deep Crawling**: Automatically checks `/contact`, `/about`, and other relevant pages if data is missing on the homepage.
- **🛡️ Evasion & Reliability**:
  - Auto-rotates User-Agents (including MS Edge/Chrome).
  - Handles rate limits (429) with intelligent backoff.
  - Proxy support (SOCKS5/HTTP).
- **💾 Auto-Save**: Saves data in real-time to `results.jsonl` to prevent data loss.

## 🛠️ Installation

1.  **Install Python 3.8+**
2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## 🚀 Usage

### 1. Prepare your URLs

Create a text file (e.g., `targets.txt`) with one URL per line:

```text
https://example.com
https://another-site.com
```

### 2. Run the Scraper

```bash
python scraper.py targets.txt
```

### 3. (Optional) Use Proxies

To prevent blocking when scraping thousands of sites, create a `proxies.txt` file in the same folder:

```text
http://user:pass@1.2.3.4:8080
socks5://user:pass@5.6.7.8:1080
```

## ⚙️ Configuration

You can tune the performance in `scraper.py`:

```python
class Config:
    MAX_CONCURRENCY = 50   # ⬆️ Increase for speed (needs good proxies)
    TIMEOUT = 15           # ⬇️ Decrease to skip slow sites faster
```

## 📂 Output Format (`results.jsonl`)

The script generates a JSONL file where each line is a valid JSON object:

```json
{
  "url": "https://example.com",
  "emails": ["contact@example.com"],
  "socials": {
    "linkedin": ["https://linkedin.com/company/example"],
    "twitter": ["https://twitter.com/example"]
  },
  "status": "success"
}
```

---

**⚠️ Disclaimer**: Use this tool responsibly. Respect `robots.txt` and the Terms of Service of the websites you scrape.
