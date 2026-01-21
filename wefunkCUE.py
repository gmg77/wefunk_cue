#!/usr/bin/python3

'''
WEFUNK RADIO wefunk-cue-grabber2 electric bugaloo
Usage: 
  python wefunkcue.py 386            (Download specific show)
  python wefunkcue.py --start 1 --end 10 (Download range)
'''

import argparse
import os
import urllib.request
import urllib.error
from urllib.parse import urlparse
from lxml import html
from datetime import datetime, timedelta
import re
import json
import sys

# Constants
WEFUNK_SHOW_URL = 'http://www.wefunkradio.com/show/'
WEFUNK_STREAM_URL = 'https://www.wefunkradio.com/mirror/stream/'

class Client:
    def GetShowContext(self, show_number):
        print(f"Processing Show {show_number}...", end=" ", flush=True)

        # 1. Fetch HTML
        html_bytes = self._fetch_show_html(show_number)
        if not html_bytes:
            print("Skipped (Could not fetch HTML).")
            return None, None, None

        # 2. Try to get Filename from Server
        real_filename = self._resolve_server_filename(show_number)
        
        # 3. Determine Date
        show_date = None
        
        # A) Try extracting from the server filename
        if real_filename:
            date_match = re.search(r'_(\d{4}-\d{2}-\d{2})', real_filename)
            if date_match:
                show_date = self._parse_date_str(date_match.group(1))

        # B) Try extracting from HTML if A failed
        if not show_date:
            show_date = self._extract_date_from_html(html_bytes)

        # C) FALLBACK: Use placeholder
        if not show_date:
            print("[Warning: Date not found, using 1970-01-01]", end=" ")
            show_date = datetime(1970, 1, 1)
            
        # 4. Finalize Filename
        if not real_filename:
            base = f"WEFUNK_Show_{show_number}_{show_date.strftime('%Y-%m-%d')}"
            suffix = "_hq.mp3" if show_number >= 360 else ".mp3"
            real_filename = base + suffix
            
        print(f"OK ({real_filename})")
        return ShowInfo(str(show_number), show_date), real_filename, html_bytes

    def _fetch_show_html(self, show_number):
        url = WEFUNK_SHOW_URL + str(show_number)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req)
            final_url = response.geturl()
            if "/shows" in final_url or final_url.rstrip('/') == "http://www.wefunkradio.com":
                 return None
            return response.read()
        except Exception:
            return None

    def _resolve_server_filename(self, show_number):
        try:
            req = urllib.request.Request(WEFUNK_STREAM_URL + str(show_number), method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=5)
            path = urlparse(response.geturl()).path
            filename = os.path.basename(path)
            if filename.lower().endswith('.mp3') and "WEFUNK_Show" in filename:
                return filename
        except Exception:
            pass
        return None

    def _extract_date_from_html(self, html_bytes):
        try:
            content = html_bytes.decode('utf-8', errors='ignore')
            
            m = re.search(r'var\s+showdate\s*=\s*[\'"](\d{4}-\d{2}-\d{2})[\'"]', content)
            if m: return self._parse_date_str(m.group(1))

            m = re.search(r'id=[\'"]sp_(\d{4}-\d{2}-\d{2})[\'"]', content)
            if m: return self._parse_date_str(m.group(1))

            tree = html.fromstring(html_bytes)
            title = tree.xpath("//title/text()")
            if title:
                m = re.search(r'\((\d{4}-\d{2}-\d{2})\)', title[0])
                if m: return self._parse_date_str(m.group(1))
        except Exception:
            pass
        return None

    def _parse_date_str(self, date_str):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return None

    def CreateCueSheet(self, show_info, filename, html_bytes):
        tracks = self._extract_tracks(html_bytes)
        if not tracks:
            print("   [Warning] No tracks found in HTML.", end=" ")
            return None
        
        cue = CueSheet("HipHop", show_info.showDate.strftime('%Y'), "WEFUNK RADIO", f"WEFUNK SHOW #{show_info.showNumber}", filename)
        for track in tracks:
            cue.addTrack(track)
        return cue

    def _extract_tracks(self, html_bytes):
        try:
            content = html_bytes.decode('utf-8', errors='ignore')
            tree = html.fromstring(html_bytes)
            
            # Extract JSON strings
            js_extra = re.search(r'var\s+trackextra\s*=\s*(.*?);', content, re.DOTALL)
            js_tracks = re.search(r'var\s+tracks\s*=\s*(.*?);', content, re.DOTALL)
            
            if not js_extra or not js_tracks: return []

            # jsonTrackExtraLst (Metadata)
            extra_data = json.loads(js_extra.group(1))
            
            # jsonTrackList (Timing)
            raw_track_data = json.loads(js_tracks.group(1))
            
            if isinstance(raw_track_data, list):
                track_data = raw_track_data
            elif isinstance(raw_track_data, dict):
                track_data = raw_track_data.get('tracks', [])
            else:
                track_data = []

            # Select the list items (li)
            pl_items = tree.xpath('//ul[@class="playlistregular"]/li')
            
            track_list = []
            
            for i, item_container in enumerate(extra_data):
                if i >= len(track_data): break
                
                if 'mspos' not in track_data[i]: continue
                mspos = timedelta(milliseconds=track_data[i]['mspos'])
                
                # --- Get Visual Text ---
                visual_text = ""
                visual_html = ""
                if i < len(pl_items):
                    content_divs = pl_items[i].xpath('.//div[@class="content"]')
                    if content_divs:
                        visual_text = content_divs[0].text_content().strip()
                        visual_html = html.tostring(content_divs[0]).decode('utf-8', errors='ignore')
                
                # Clean up multiple spaces/newlines in visual text
                visual_text = re.sub(r'\s+', ' ', visual_text) 
                
                if i == 0:
                    track_list.append(Track(1, "WEFUNK RADIO", "intro", mspos))
                else:
                    json_artist = ''
                    json_title = ''
                    
                    # 1. Get JSON Metadata
                    if isinstance(item_container, list) and len(item_container) > 0:
                        info = item_container[0]
                        json_artist = info.get('a', '')
                        json_title = info.get('t', '')
                    elif isinstance(item_container, dict):
                         json_artist = item_container.get('a', '')
                         json_title = item_container.get('t', '')
                    
                    if json_artist: json_artist = json_artist.strip()
                    if json_title: json_title = json_title.strip()

                    # 2. Heuristics
                    is_talk_tag = "<strong>talk</strong>" in visual_html
                    is_interview_text = "interview" in visual_text.lower()
                    
                    # 3. Determine Final Artist/Title
                    
                    # PRIORITY 1: If it's an interview, FORCE usage of Visual Text
                    if is_interview_text:
                        final_artist = "WEFUNK RADIO"
                        final_title = visual_text
                    
                    # PRIORITY 2: If JSON data is missing, fallback to Visual Text
                    elif not json_artist and not json_title:
                        final_artist = "WEFUNK RADIO"
                        final_title = visual_text if visual_text else "Unknown"
                        
                    # PRIORITY 3: Standard Song (JSON data exists and not an interview)
                    else:
                        final_artist = json_artist
                        final_title = json_title
                        
                        # Handle Talkover tag for standard songs
                        if is_talk_tag:
                            if final_title and final_title != "Unknown" and final_title != visual_text:
                                final_title = f"talk (over {final_artist} - {final_title})"
                            else:
                                final_title = "talk"
                            final_artist = "WEFUNK RADIO"

                    track_list.append(Track(i + 1, final_artist, final_title, mspos))
            
            return track_list
        except Exception as e:
            print(f"   [Error parsing tracks: {e}]", end=" ")
            return []

class Track:    
    def __init__(self, nr, artist, title, startsAt):
        self.nr = nr
        self.artist = artist
        self.title = title
        self.startsAt = startsAt
        
class ShowInfo:
    def __init__(self, showNumber, showDate):
        self.showNumber = showNumber
        self.showDate = showDate
        
class CueSheet:
    def __init__(self, genre, year, performer, title, fileName):
        self.genre = genre
        self.year = year
        self.performer = performer
        self.title = title
        self.fileName = fileName
        self.tracks = []
        
    def addTrack(self, track):
        self.tracks.append(track)        
        
    def saveToFile(self, path):    
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'TITLE "{self.title}"')
            f.write(f'\nPERFORMER "{self.performer}"')
            f.write(f'\nREM Year  : {self.year}')
            f.write(f'\nREM Genre : {self.genre}')
            f.write(f'\nFILE "{self.fileName}" MP3')
            
            for track in self.tracks:
                mins = int(track.startsAt.total_seconds() // 60)
                secs = int(track.startsAt.total_seconds() % 60)
                frames = int((track.startsAt.microseconds / 1000) * 0.075)
                
                f.write(f"\n\tTRACK {track.nr:02d} AUDIO")
                title_clean = track.title.replace('"', "'")
                artist_clean = track.artist.replace('"', "'")
                f.write(f'\n\t\tTITLE "{title_clean}"')
                f.write(f'\n\t\tPERFORMER "{artist_clean}"')
                f.write(f"\n\t\tINDEX 01 {mins:02d}:{secs:02d}:{frames:02d}")

# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Downloads cue sheets for WEFUNK RADIO.")
    
    # NEW: Optional positional argument for single show
    parser.add_argument("show", nargs="?", type=int, help="Single show number to download (e.g. 1234)")
    
    parser.add_argument("-o", "--output-dir", default="mp3s", help="Output directory (default: mp3s)")
    parser.add_argument("--start", type=int, help="Start show number (for ranges)")
    parser.add_argument("--end", type=int, help="End show number (for ranges)")
    args = parser.parse_args()
    
    # If the positional argument is used, it overrides start/end
    if args.show is not None:
        args.start = args.show
        args.end = args.show
    
    # Interactive fallback
    if args.start is None:
        try: args.start = int(input("Start Show: "))
        except ValueError: sys.exit(1)
    if args.end is None:
        # If user only enters start in interactive mode, default end to start (single show)
        try: 
            val = input("End Show (Enter for same): ")
            args.end = int(val) if val else args.start
        except ValueError: sys.exit(1)

    if args.end < args.start:
        print("Error: End number cannot be smaller than start.")
        sys.exit(1)

    if not os.path.exists(args.output_dir):
        try:
            os.makedirs(args.output_dir)
            print(f"Created directory: {os.path.abspath(args.output_dir)}")
        except Exception as e:
            print(f"Error creating directory {args.output_dir}: {e}")
            sys.exit(1)
    
    client = Client()

    for number in range(args.start, args.end + 1):
        show_info, filename, html_bytes = client.GetShowContext(number)
        
        if show_info and filename and html_bytes:
            cue = client.CreateCueSheet(show_info, filename, html_bytes)
            if cue:
                cue_name = filename[:-4] + ".cue" if filename.endswith(".mp3") else filename + ".cue"
                full_path = os.path.join(args.output_dir, cue_name)
                try:
                    cue.saveToFile(full_path)
                    print(f"   [Cue] Saved to {cue_name}")
                except Exception as e:
                    print(f"   [Error] Could not write file: {e}")
            
    print("\nDone.")

if __name__ == "__main__":
    main()