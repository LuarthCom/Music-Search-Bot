"""
Music Search Bot adaptado para aplicação web.
"""
import logging
import time
import random
from typing import Optional, Dict, List, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
import json
import re
import unicodedata
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from ytmusicapi import YTMusic


def normalize_text(text):
    """Normaliza texto removendo acentos e caracteres especiais."""
    if not text:
        return ""
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    return text.lower().strip()


def clean_query(track_name, artist_name):
    """Limpa e normaliza uma query de busca musical."""
    if not track_name or not artist_name:
        return ""
    
    remove_terms = [
        'feat', 'featuring', 'ft', 'remix', 'edit', 'mix', 'version',
        'remaster', 'remastered', 'radio edit', 'extended', 'club mix',
        'acoustic', 'live', 'demo', 'instrumental', 'karaoke'
    ]
    
    clean_track = track_name.strip()
    clean_track = re.sub(r'\([^)]*\)', '', clean_track)
    clean_track = re.sub(r'\[[^\]]*\]', '', clean_track)
    
    for term in remove_terms:
        pattern = r'\b' + re.escape(term) + r'\b.*'
        clean_track = re.sub(pattern, '', clean_track, flags=re.IGNORECASE)
    
    clean_artist = artist_name.strip()
    clean_artist = re.sub(r'\([^)]*\)', '', clean_artist)
    clean_artist = re.sub(r'\[[^\]]*\]', '', clean_artist)
    
    clean_track = re.sub(r'\s+', ' ', clean_track).strip()
    clean_artist = re.sub(r'\s+', ' ', clean_artist).strip()
    
    clean_track = normalize_text(clean_track)
    clean_artist = normalize_text(clean_artist)
    
    return f"{clean_track} {clean_artist}".strip()


def generate_search_variants(track_name, artist_name):
    """Gera variantes de busca para aumentar chances de sucesso."""
    variants = []
    
    main_query = clean_query(track_name, artist_name)
    if main_query:
        variants.append(main_query)
    
    clean_track = normalize_text(track_name.strip())
    clean_artist = normalize_text(artist_name.strip())
    
    if clean_artist and clean_track:
        variants.append(f"{clean_artist} {clean_track}")
    
    if clean_track and len(clean_track) > 3:
        variants.append(clean_track)
    
    seen = set()
    unique_variants = []
    for variant in variants:
        if variant and variant not in seen:
            seen.add(variant)
            unique_variants.append(variant)
    
    return unique_variants[:3]


def is_valid_youtube_url(url):
    """Valida se uma URL do YouTube é válida."""
    if not url:
        return False
    youtube_pattern = r'https://www\.youtube\.com/watch\?v=.{11}'
    return bool(re.match(youtube_pattern, url))


class YouTubeMusicSearcher:
    def __init__(self):
        self.ytmusic = None
        self._initialize()
    
    def _initialize(self):
        try:
            self.ytmusic = YTMusic()
        except Exception:
            self.ytmusic = None
    
    def search(self, query: str, max_results: int = 5) -> Optional[str]:
        if not self.ytmusic or not query:
            return None
        
        try:
            results = self.ytmusic.search(query, filter="songs", limit=max_results)
            
            for result in results:
                if self._is_valid_music_result(result):
                    video_id = result.get('videoId')
                    if video_id:
                        return f"https://www.youtube.com/watch?v={video_id}"
            
            results = self.ytmusic.search(query, limit=max_results)
            for result in results:
                if self._is_valid_music_result(result):
                    video_id = result.get('videoId')
                    if video_id:
                        return f"https://www.youtube.com/watch?v={video_id}"
                        
        except Exception:
            pass
        
        return None
    
    def _is_valid_music_result(self, result: dict) -> bool:
        if not result or not result.get('videoId'):
            return False
        
        title = result.get('title', '').lower()
        result_type = result.get('resultType', '').lower()
        category = result.get('category', '').lower()
        
        if result_type in ['song', 'video'] or category in ['songs', 'music']:
            return True
        
        avoid_terms = ['playlist', 'album', 'artist', 'interview', 'documentary']
        if any(term in result_type for term in avoid_terms):
            return False
        
        avoid_in_title = ['interview', 'documentary', 'behind the scenes', 'making of']
        if any(term in title for term in avoid_in_title):
            return False
        
        return True
    
    def is_available(self) -> bool:
        return self.ytmusic is not None


class YouTubeScraper:
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(headers)
    
    def search(self, query: str, max_retries: int = 2) -> Optional[str]:
        if not query:
            return None
        
        for attempt in range(max_retries):
            try:
                url = self._search_attempt(query)
                if url:
                    return url
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
        
        return None
    
    def _search_attempt(self, query: str) -> Optional[str]:
        encoded_query = quote_plus(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}&hl=en&gl=US"
        
        response = self.session.get(search_url, timeout=self.timeout)
        response.raise_for_status()
        
        yt_initial_data = self._extract_yt_initial_data(response.text)
        if not yt_initial_data:
            return None
        
        video_id = self._find_first_video_id(yt_initial_data)
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        
        return None
    
    def _extract_yt_initial_data(self, html: str) -> Optional[dict]:
        try:
            pattern = r'var ytInitialData = ({.*?});'
            match = re.search(pattern, html)
            
            if not match:
                pattern = r'window\["ytInitialData"\] = ({.*?});'
                match = re.search(pattern, html)
            
            if match:
                json_str = match.group(1)
                return json.loads(json_str)
        except:
            pass
        
        return None
    
    def _find_first_video_id(self, yt_data: dict) -> Optional[str]:
        try:
            return self._recursive_search_video_id(yt_data, max_depth=10)
        except:
            return None
    
    def _recursive_search_video_id(self, data, max_depth: int = 10) -> Optional[str]:
        if max_depth <= 0:
            return None
        
        if isinstance(data, dict):
            if 'videoId' in data:
                video_id = data['videoId']
                if self._is_valid_video_id(video_id):
                    return video_id
            
            for value in data.values():
                result = self._recursive_search_video_id(value, max_depth - 1)
                if result:
                    return result
        
        elif isinstance(data, list):
            for item in data:
                result = self._recursive_search_video_id(item, max_depth - 1)
                if result:
                    return result
        
        return None
    
    def _is_valid_video_id(self, video_id: str) -> bool:
        if not video_id or not isinstance(video_id, str):
            return False
        return len(video_id) == 11 and re.match(r'^[a-zA-Z0-9_-]+$', video_id)


class FourSharedScraper:
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.base_url = "https://www.4shared.com"
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://www.4shared.com/',
        }
        self.session.headers.update(headers)
    
    def search(self, query: str, track_name: str = "", artist_name: str = "", max_retries: int = 2) -> Optional[str]:
        if not query:
            return None
        
        for attempt in range(max_retries):
            try:
                url = self._search_attempt(query, track_name, artist_name)
                if url:
                    return url
                if attempt < max_retries - 1:
                    time.sleep(1.5 * (attempt + 1))
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
        
        return None
    
    def _search_attempt(self, query: str, track_name: str, artist_name: str) -> Optional[str]:
        encoded_query = quote_plus(query)
        search_url = f"{self.base_url}/web/q?query={encoded_query}"
        
        response = self.session.get(search_url, timeout=self.timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        audio_links = self._find_audio_links(soup, track_name, artist_name)
        
        if audio_links:
            best_link = self._select_best_link(audio_links, track_name, artist_name)
            if best_link:
                return self._normalize_4shared_url(best_link)
        
        return None
    
    def _find_audio_links(self, soup: BeautifulSoup, track_name: str, artist_name: str) -> List[dict]:
        audio_links = []
        
        selectors = [
            'div.searchItemContainer',
            'div.searchItem',
            'div.item',
            '.search-item',
            '.file-item',
            'tr.searchItem'
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            if items:
                for item in items:
                    link_data = self._extract_link_from_item(item, track_name, artist_name)
                    if link_data:
                        audio_links.append(link_data)
                break
        
        if not audio_links:
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                if self._looks_like_audio_link(href, text):
                    link_data = {
                        'url': href,
                        'title': text,
                        'relevance': self._calculate_relevance(text, track_name, artist_name)
                    }
                    audio_links.append(link_data)
        
        return audio_links
    
    def _extract_link_from_item(self, item, track_name: str, artist_name: str) -> Optional[dict]:
        link_selectors = [
            'a[href*="/file/"]',
            'a[href*="/audio/"]',
            'a[href*="/get/"]',
            'a[href*="/download/"]',
            'a.fileName',
            'a.fileLink'
        ]
        
        for selector in link_selectors:
            link = item.select_one(selector)
            if link:
                href = link.get('href', '')
                title = link.get_text(strip=True)
                
                if href and self._looks_like_audio_link(href, title):
                    return {
                        'url': href,
                        'title': title,
                        'relevance': self._calculate_relevance(title, track_name, artist_name)
                    }
        
        all_links = item.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            title = link.get_text(strip=True)
            
            if self._looks_like_audio_link(href, title):
                return {
                    'url': href,
                    'title': title,
                    'relevance': self._calculate_relevance(title, track_name, artist_name)
                }
        
        return None
    
    def _looks_like_audio_link(self, href: str, text: str) -> bool:
        if not href:
            return False
        
        audio_patterns = ['/file/', '/audio/', '/get/', '/download/', '.mp3', '.m4a', '.wav', '.flac']
        if any(pattern in href.lower() for pattern in audio_patterns):
            return True
        
        audio_extensions = ['.mp3', '.m4a', '.wav', '.flac', '.aac', '.ogg']
        if any(ext in text.lower() for ext in audio_extensions):
            return True
        
        avoid_patterns = ['/folder/', '/album/', '/playlist/', 'javascript:', 'mailto:', '#']
        if any(pattern in href.lower() for pattern in avoid_patterns):
            return False
        
        return len(text.strip()) > 3
    
    def _calculate_relevance(self, title: str, track_name: str, artist_name: str) -> float:
        if not title:
            return 0.0
        
        title_normalized = normalize_text(title)
        track_normalized = normalize_text(track_name) if track_name else ""
        artist_normalized = normalize_text(artist_name) if artist_name else ""
        
        relevance = 0.0
        
        if track_normalized and track_normalized in title_normalized:
            relevance += 0.5
        
        if artist_normalized and artist_normalized in title_normalized:
            relevance += 0.3
        
        audio_extensions = ['.mp3', '.m4a', '.wav', '.flac', '.aac']
        if any(ext in title_normalized for ext in audio_extensions):
            relevance += 0.2
        
        avoid_terms = ['remix', 'karaoke', 'instrumental', 'cover', 'live']
        for term in avoid_terms:
            if term in title_normalized:
                relevance -= 0.1
        
        return max(0.0, relevance)
    
    def _select_best_link(self, links: List[dict], track_name: str, artist_name: str) -> Optional[str]:
        if not links:
            return None
        
        sorted_links = sorted(links, key=lambda x: x.get('relevance', 0), reverse=True)
        return sorted_links[0]['url']
    
    def _normalize_4shared_url(self, url: str) -> str:
        if not url:
            return ""
        
        if url.startswith('http'):
            return url
        
        if url.startswith('//'):
            return f"https:{url}"
        
        if url.startswith('/'):
            return f"{self.base_url}{url}"
        
        return url


class MusicSearchBot:
    def __init__(self, delay: float = 1.5, max_retries: int = 3, concurrency: int = 2, timeout: int = 10):
        self.delay = delay
        self.max_retries = max_retries
        self.concurrency = min(concurrency, 3)
        self.timeout = timeout
        
        self.youtube_music = YouTubeMusicSearcher()
        self.youtube_scraper = YouTubeScraper(timeout=timeout)
        self.fourshared_scraper = FourSharedScraper(timeout=timeout)
        
        self.stats = {
            'total_songs': 0,
            'youtube_found': 0,
            'fourshared_found': 0,
            'not_found': 0,
            'errors': 0
        }
    
    def search_single_track(self, track_name: str, artist_name: str) -> Dict[str, str]:
        result = {
            'track_name': track_name,
            'artist_name': artist_name,
            'youtube_url': '',
            'fourshared_url': '',
            'status': 'not_found'
        }
        
        self.stats['total_songs'] += 1
        
        try:
            search_variants = generate_search_variants(track_name, artist_name)
            
            if not search_variants:
                self.stats['errors'] += 1
                result['status'] = 'error'
                return result
            
            for variant in search_variants:
                youtube_url = self._search_youtube(variant)
                if youtube_url:
                    result['youtube_url'] = youtube_url
                    result['status'] = 'found'
                    self.stats['youtube_found'] += 1
                    return result
                
                fourshared_url = self._search_fourshared(variant, track_name, artist_name)
                if fourshared_url:
                    result['fourshared_url'] = fourshared_url
                    result['status'] = 'found'
                    self.stats['fourshared_found'] += 1
                    return result
                
                if variant != search_variants[-1]:
                    time.sleep(self.delay * 0.5)
            
            self.stats['not_found'] += 1
            
        except Exception:
            self.stats['errors'] += 1
            result['status'] = 'error'
        
        return result
    
    def _search_youtube(self, query: str) -> Optional[str]:
        if self.youtube_music.is_available():
            url = self._search_with_retries(lambda: self.youtube_music.search(query))
            if url and is_valid_youtube_url(url):
                return url
        
        url = self._search_with_retries(lambda: self.youtube_scraper.search(query))
        if url and is_valid_youtube_url(url):
            return url
        
        return None
    
    def _search_fourshared(self, query: str, track_name: str, artist_name: str) -> Optional[str]:
        return self._search_with_retries(
            lambda: self.fourshared_scraper.search(query, track_name, artist_name)
        )
    
    def _search_with_retries(self, search_func) -> Optional[str]:
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    backoff_delay = self.delay * (2 ** attempt) + random.uniform(0.1, 0.5)
                    backoff_delay = min(backoff_delay, 10.0)
                    time.sleep(backoff_delay)
                
                result = search_func()
                if result:
                    return result
                    
            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    self.delay = min(self.delay * 1.5, 5.0)
                    retry_after = e.response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                            time.sleep(wait_time)
                        except ValueError:
                            time.sleep(self.delay * 2)
                    else:
                        time.sleep(self.delay * 2)
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay * (attempt + 1))
        
        return None


def run_playlist(input_csv_path: str, output_csv_path: str, output_xlsx_path: str, 
                delay: float, max_retries: int, concurrency: int, 
                progress_callback: Callable[[int, int, dict, str], None]):
    """
    Processa playlist com callback de progresso.
    """
    try:
        df = pd.read_csv(input_csv_path, encoding='utf-8')
        
        # Detecta e mapeia colunas
        columns = _detect_and_map_columns(df)
        if not columns:
            raise ValueError("CSV deve conter colunas 'Track Name' e 'Artist Name(s)' ou 'Música' e 'Artista'")
        
        track_col, artist_col = columns
        
        # Prepara dados
        tracks_data = []
        for idx, row in df.iterrows():
            track_name = str(row[track_col]).strip() if pd.notna(row[track_col]) else ""
            artist_name = str(row[artist_col]).strip() if pd.notna(row[artist_col]) else ""
            
            if track_name and artist_name:
                tracks_data.append({
                    'index': idx,
                    'track_name': track_name,
                    'artist_name': artist_name
                })
        
        if not tracks_data:
            raise ValueError("Nenhuma música válida encontrada no CSV")
        
        # Inicializa bot
        bot = MusicSearchBot(delay=delay, max_retries=max_retries, concurrency=concurrency)
        
        # Processa músicas
        results = []
        total = len(tracks_data)
        
        for i, track_data in enumerate(tracks_data):
            try:
                result = bot.search_single_track(track_data['track_name'], track_data['artist_name'])
                result['index'] = track_data['index']
                results.append(result)
                
                # Callback de progresso
                last_message = f"{track_data['track_name']} - {track_data['artist_name']}"
                progress_callback(i + 1, total, bot.stats.copy(), last_message)
                
                # Delay entre buscas
                if i < total - 1:
                    time.sleep(delay)
                    
            except Exception:
                results.append({
                    'index': track_data['index'],
                    'track_name': track_data['track_name'],
                    'artist_name': track_data['artist_name'],
                    'youtube_url': '',
                    'fourshared_url': '',
                    'status': 'error'
                })
        
        # Adiciona resultados ao DataFrame
        df['Link YouTube'] = ''
        df['Link 4shared'] = ''
        df['Status'] = 'not_found'
        
        for result in results:
            idx = result['index']
            df.at[idx, 'Link YouTube'] = result['youtube_url']
            df.at[idx, 'Link 4shared'] = result['fourshared_url']
            df.at[idx, 'Status'] = result['status']
        
        # Salva arquivos
        df.to_csv(output_csv_path, index=False, encoding='utf-8')
        df.to_excel(output_xlsx_path, index=False)
        
        return bot.stats
        
    except Exception as e:
        raise Exception(f"Erro no processamento: {str(e)}")


def _detect_and_map_columns(df: pd.DataFrame) -> Optional[tuple]:
    """Detecta e mapeia colunas do CSV."""
    columns = df.columns.tolist()
    
    # Verifica formato Exportify
    if 'Track Name' in columns and 'Artist Name(s)' in columns:
        return ('Track Name', 'Artist Name(s)')
    
    # Verifica formato manual português
    if 'Música' in columns and 'Artista' in columns:
        return ('Música', 'Artista')
    
    return None

