# Utility functions for Business Intelligence Analyzer
import re
import time
import hashlib
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class InputProcessor:
    """Processore intelligente per input utente"""
    
    @staticmethod
    def identify_input_type(user_input: str) -> Dict[str, Any]:
        """Identifica il tipo di input fornito dall'utente"""
        user_input = user_input.strip()
        
        result = {
            'original_input': user_input,
            'input_type': 'unknown',
            'extracted_data': {},
            'confidence': 0.0
        }
        
        # Check se è un URL
        if user_input.startswith(('http://', 'https://')):
            result['input_type'] = 'url'
            result['extracted_data']['url'] = user_input
            result['extracted_data']['domain'] = urlparse(user_input).netloc
            result['confidence'] = 1.0
            return result
        
        # Check se è una Partita IVA italiana (11 cifre)
        piva_match = re.search(r'\b\d{11}\b', user_input)
        if piva_match:
            result['input_type'] = 'partita_iva'
            result['extracted_data']['partita_iva'] = piva_match.group()
            result['confidence'] = 0.9
            
            # Prova a estrarre anche il nome azienda se presente
            company_name = re.sub(r'\b\d{11}\b', '', user_input).strip()
            if company_name:
                result['extracted_data']['company_name'] = company_name
            return result
        
        # Check se è un dominio (senza http)
        domain_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$'
        if re.match(domain_pattern, user_input):
            result['input_type'] = 'domain'
            result['extracted_data']['domain'] = user_input
            result['confidence'] = 0.8
            return result
        
        # Check se contiene un dominio
        domain_in_text = re.search(r'\b([a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,})\b', user_input)
        if domain_in_text:
            result['input_type'] = 'company_with_domain'
            result['extracted_data']['domain'] = domain_in_text.group(1)
            result['extracted_data']['company_name'] = user_input.replace(domain_in_text.group(1), '').strip()
            result['confidence'] = 0.7
            return result
        
        # Default: nome azienda
        result['input_type'] = 'company_name'
        result['extracted_data']['company_name'] = user_input
        result['confidence'] = 0.5
        
        return result
    
    @staticmethod
    def clean_company_name(company_name: str) -> str:
        """Pulisce e normalizza il nome azienda"""
        # Rimuovi forme giuridiche comuni
        legal_forms = [
            r'\bsrl\b', r'\bs\.r\.l\.\b', r'\bs\.r\.l\b',
            r'\bspa\b', r'\bs\.p\.a\.\b', r'\bs\.p\.a\b',
            r'\bsnc\b', r'\bs\.n\.c\.\b', r'\bs\.n\.c\b',
            r'\bsas\b', r'\bs\.a\.s\.\b', r'\bs\.a\.s\b',
            r'\bltd\b', r'\bllc\b', r'\binc\b', r'\bcorp\b'
        ]
        
        cleaned = company_name
        for form in legal_forms:
            cleaned = re.sub(form, '', cleaned, flags=re.IGNORECASE)
        
        # Pulisci spazi extra e caratteri speciali
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        cleaned = re.sub(r'[^\w\s-]', '', cleaned)
        
        return cleaned
    
    @staticmethod
    def extract_domain_suggestions(company_name: str) -> List[str]:
        """Genera possibili domini basati sul nome azienda"""
        clean_name = InputProcessor.clean_company_name(company_name)
        
        # Rimuovi spazi e caratteri speciali
        domain_base = re.sub(r'[^\w]', '', clean_name.lower())
        
        suggestions = [
            f"{domain_base}.it",
            f"{domain_base}.com", 
            f"www.{domain_base}.it",
            f"www.{domain_base}.com"
        ]
        
        # Aggiungi varianti con trattini
        if len(clean_name.split()) > 1:
            words = [word.lower() for word in clean_name.split()]
            hyphenated = '-'.join(words)
            suggestions.extend([
                f"{hyphenated}.it",
                f"{hyphenated}.com"
            ])
        
        return suggestions

class DataEnricher:
    """Arricchimento dati tramite web scraping intelligente"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    async def enrich_company_data(self, basic_data: Dict[str, Any]) -> Dict[str, Any]:
        """Arricchisce i dati aziendali base"""
        enriched = basic_data.copy()
        
        # Se abbiamo un dominio, prova a estrarre informazioni dal sito
        if 'domain' in basic_data:
            website_data = await self._scrape_website_info(basic_data['domain'])
            enriched.update(website_data)
        
        # Se abbiamo P.IVA, cerca su registri pubblici
        if 'partita_iva' in basic_data:
            registry_data = await self._search_business_registries(basic_data['partita_iva'])
            enriched.update(registry_data)
        
        return enriched
    
    async def _scrape_website_info(self, domain: str) -> Dict[str, Any]:
        """Estrae informazioni dal sito web aziendale"""
        info = {
            'website_title': '',
            'website_description': '',
            'contact_info': {},
            'social_links': {},
            'business_info': {}
        }
        
        try:
            if not domain.startswith(('http://', 'https://')):
                url = f"https://{domain}"
            else:
                url = domain
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Estrai title e description
            title_tag = soup.find('title')
            if title_tag:
                info['website_title'] = title_tag.get_text().strip()
            
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                info['website_description'] = meta_desc.get('content', '').strip()
            
            # Cerca link social
            social_patterns = {
                'facebook': r'facebook\.com/[^/\s"\']+',
                'instagram': r'instagram\.com/[^/\s"\']+',
                'linkedin': r'linkedin\.com/company/[^/\s"\']+',
                'youtube': r'youtube\.com/[^/\s"\']+',
                'twitter': r'twitter\.com/[^/\s"\']+',
                'tiktok': r'tiktok\.com/@[^/\s"\']+'
            }
            
            page_text = soup.get_text()
            for platform, pattern in social_patterns.items():
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    info['social_links'][platform] = f"https://{matches[0]}"
            
            # Cerca informazioni di contatto
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            phone_pattern = r'(\+39\s?)?[\d\s\-\(\)]{8,15}'
            
            emails = re.findall(email_pattern, page_text)
            phones = re.findall(phone_pattern, page_text)
            
            if emails:
                info['contact_info']['emails'] = list(set(emails))
            if phones:
                info['contact_info']['phones'] = list(set(phones))
            
        except Exception as e:
            logger.warning(f"Errore scraping {domain}: {e}")
        
        return info
    
    async def _search_business_registries(self, partita_iva: str) -> Dict[str, Any]:
        """Cerca informazioni nei registri delle imprese"""
        registry_info = {
            'registry_data': {},
            'financial_summary': {},
            'legal_info': {}
        }
        
        # Implementazione semplificata - in produzione integrare con API ufficiali
        # o servizi di business intelligence come Aida, InfoCamere, etc.
        
        try:
            # Simula ricerca su registri pubblici
            # In produzione, implementare chiamate effettive ai servizi
            
            registry_info['registry_data'] = {
                'partita_iva': partita_iva,
                'search_attempted': True,
                'sources_checked': [
                    'registro-imprese.it',
                    'ufficiocamerale.it',
                    'reportaziende.it'
                ],
                'data_found': False,
                'note': 'Implementazione API registri in sviluppo'
            }
            
        except Exception as e:
            logger.warning(f"Errore ricerca registri per P.IVA {partita_iva}: {e}")
        
        return registry_info

class RateLimiter:
    """Gestione rate limiting per API multiple"""
    
    def __init__(self):
        self.api_calls = {}
        self.rate_limits = {
            'semrush': {'calls': 0, 'limit': 10, 'window': 60},
            'serper': {'calls': 0, 'limit': 100, 'window': 60},
            'openai': {'calls': 0, 'limit': 50, 'window': 60}
        }
        self.last_reset = datetime.now()
    
    def can_make_call(self, api_name: str) -> bool:
        """Verifica se è possibile fare una chiamata API"""
        self._reset_counters_if_needed()
        
        if api_name not in self.rate_limits:
            return True
        
        current_calls = self.rate_limits[api_name]['calls']
        limit = self.rate_limits[api_name]['limit']
        
        return current_calls < limit
    
    def record_call(self, api_name: str):
        """Registra una chiamata API"""
        if api_name in self.rate_limits:
            self.rate_limits[api_name]['calls'] += 1
    
    def get_wait_time(self, api_name: str) -> int:
        """Restituisce tempo di attesa in secondi"""
        if self.can_make_call(api_name):
            return 0
        
        if api_name in self.rate_limits:
            window = self.rate_limits[api_name]['window']
            elapsed = (datetime.now() - self.last_reset).total_seconds()
            return max(0, window - elapsed)
        
        return 0
    
    def _reset_counters_if_needed(self):
        """Reset contatori se la finestra temporale è scaduta"""
        now = datetime.now()
        if (now - self.last_reset).total_seconds() >= 60:  # Reset ogni minuto
            for api in self.rate_limits:
                self.rate_limits[api]['calls'] = 0
            self.last_reset = now

class CacheManager:
    """Gestione cache per ottimizzare chiamate API"""
    
    def __init__(self, cache_duration_hours: int = 24):
        self.cache = {}
        self.cache_duration = timedelta(hours=cache_duration_hours)
    
    def get_cache_key(self, api_name: str, params: Dict[str, Any]) -> str:
        """Genera chiave cache univoca"""
        # Serializza parametri in modo deterministico
        params_str = json.dumps(params, sort_keys=True)
        cache_input = f"{api_name}:{params_str}"
        return hashlib.md5(cache_input.encode()).hexdigest()
    
    def get(self, cache_key: str) -> Optional[Any]:
        """Recupera dati dalla cache se validi"""
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < self.cache_duration:
                logger.info(f"Cache hit per chiave: {cache_key[:8]}...")
                return cached_data
            else:
                # Rimuovi dati scaduti
                del self.cache[cache_key]
        
        return None
    
    def set(self, cache_key: str, data: Any):
        """Salva dati in cache"""
        self.cache[cache_key] = (data, datetime.now())
        logger.info(f"Dati salvati in cache: {cache_key[:8]}...")
    
    def clear_expired(self):
        """Rimuove dati scaduti dalla cache"""
        now = datetime.now()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if now - timestamp >= self.cache_duration
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"Rimossi {len(expired_keys)} elementi scaduti dalla cache")

class DataValidator:
    """Validazione e sanificazione dati"""
    
    @staticmethod
    def validate_partita_iva(piva: str) -> bool:
        """Valida Partita IVA italiana"""
        # Rimuovi spazi e caratteri non numerici
        piva = re.sub(r'[^\d]', '', piva)
        
        # Deve essere esattamente 11 cifre
        if len(piva) != 11:
            return False
        
        # Algoritmo di controllo per P.IVA italiana
        try:
            # Calcola checksum
            odd_sum = sum(int(piva[i]) for i in range(0, 10, 2))
            even_sum = 0
            
            for i in range(1, 10, 2):
                digit = int(piva[i]) * 2
                even_sum += digit if digit < 10 else digit - 9
            
            total = odd_sum + even_sum
            check_digit = (10 - (total % 10)) % 10
            
            return int(piva[10]) == check_digit
        except (ValueError, IndexError):
            return False
    
    @staticmethod
    def validate_domain(domain: str) -> bool:
        """Valida formato dominio"""
        domain_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}
        return bool(re.match(domain_pattern, domain))
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Valida URL completo"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    @staticmethod
    def sanitize_company_name(name: str) -> str:
        """Sanifica nome azienda per ricerche"""
        # Rimuovi caratteri speciali pericolosi
        sanitized = re.sub(r'[<>"\'/\\{}();]', '', name)
        
        # Normalizza spazi
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized
    
    @staticmethod
    def extract_numbers(text: str) -> List[float]:
        """Estrae numeri da testo (per fatturati, dipendenti, etc.)"""
        # Pattern per numeri con separatori italiani
        number_patterns = [
            r'€\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',  # Euro
            r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*€',  # Euro alla fine
            r'(\d{1,3}(?:\.\d{3})*)',                 # Numeri con separatori
            r'(\d+,\d{2})',                           # Decimali
            r'(\d+)'                                  # Numeri semplici
        ]
        
        numbers = []
        for pattern in number_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    # Converti formato italiano in float
                    clean_number = match.replace('.', '').replace(',', '.')
                    numbers.append(float(clean_number))
                except ValueError:
                    continue
        
        return numbers

class ReportFormatter:
    """Formattazione e styling report"""
    
    @staticmethod
    def format_currency(amount: float, currency: str = "EUR") -> str:
        """Formatta valuta in formato italiano"""
        if currency == "EUR":
            return f"€ {amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"{amount:,.2f} {currency}"
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """Formatta percentuale"""
        return f"{value:.{decimals}f}%"
    
    @staticmethod
    def format_large_number(number: int) -> str:
        """Formatta numeri grandi (K, M, B)"""
        if number >= 1_000_000_000:
            return f"{number/1_000_000_000:.1f}B"
        elif number >= 1_000_000:
            return f"{number/1_000_000:.1f}M"
        elif number >= 1_000:
            return f"{number/1_000:.1f}K"
        else:
            return str(number)
    
    @staticmethod
    def create_trend_indicator(current: float, previous: float) -> str:
        """Crea indicatore di trend"""
        if previous == 0:
            return "📊 Nuovo dato"
        
        change = ((current - previous) / previous) * 100
        
        if change > 10:
            return f"📈 +{change:.1f}% (Forte crescita)"
        elif change > 0:
            return f"📈 +{change:.1f}% (Crescita)"
        elif change > -10:
            return f"📉 {change:.1f}% (Lieve calo)"
        else:
            return f"📉 {change:.1f}% (Forte calo)"
    
    @staticmethod
    def generate_executive_summary(data: Dict[str, Any]) -> str:
        """Genera executive summary da dati"""
        summary_points = []
        
        # Analisi SEO
        if 'semrush' in data and 'analysis' in data['semrush']:
            seo_data = data['semrush']['analysis']
            if 'traffico_organico' in seo_data:
                traffic = seo_data['traffico_organico']
                summary_points.append(f"🔍 Traffico organico: {ReportFormatter.format_large_number(traffic)} visite/mese")
        
        # Competitor
        if 'competitors' in data and 'competitor_analysis' in data['competitors']:
            comp_data = data['competitors']['competitor_analysis']
            if 'competitors' in comp_data:
                comp_count = len(comp_data['competitors'])
                summary_points.append(f"🏢 {comp_count} competitor principali identificati")
        
        # Social
        if 'social' in data and 'social_analysis' in data['social']:
            social_data = data['social']['social_analysis']
            total_followers = 0
            for platform in ['instagram', 'facebook', 'linkedin']:
                if platform in social_data:
                    followers = social_data[platform].get('follower_count', 0)
                    total_followers += followers
            
            if total_followers > 0:
                summary_points.append(f"📱 {ReportFormatter.format_large_number(total_followers)} follower totali sui social")
        
        # Financial
        if 'financial' in data and 'financial_analysis' in data['financial']:
            fin_data = data['financial']['financial_analysis']
            if 'fatturato_evolution' in fin_data:
                latest_year = max(fin_data['fatturato_evolution'].keys())
                revenue = fin_data['fatturato_evolution'][latest_year]
                summary_points.append(f"💰 Fatturato {latest_year}: {ReportFormatter.format_currency(revenue)}")
        
        if not summary_points:
            summary_points = ["📊 Analisi completa dei dati aziendali disponibili"]
        
        return "**KEY INSIGHTS:**\n" + "\n".join([f"• {point}" for point in summary_points])

class AsyncHelpers:
    """Helper per operazioni asincrone"""
    
    @staticmethod
    async def gather_with_timeout(tasks: List, timeout: int = 300) -> List[Any]:
        """Esegue task asincroni con timeout"""
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout
            )
            return results
        except asyncio.TimeoutError:
            logger.error(f"Timeout dopo {timeout} secondi")
            return [None] * len(tasks)
    
    @staticmethod
    async def retry_async_call(func, max_retries: int = 3, delay: float = 1.0, *args, **kwargs):
        """Retry automatico per chiamate asincrone"""
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(f"Tentativo {attempt + 1} fallito: {e}. Riprovo in {delay}s...")
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Tutti i {max_retries} tentativi falliti")
        
        raise last_exception

class ProgressTracker:
    """Tracking progresso per operazioni lunghe"""
    
    def __init__(self, total_steps: int):
        self.total_steps = total_steps
        self.current_step = 0
        self.step_descriptions = {}
        self.start_time = datetime.now()
        self.step_times = []
    
    def update(self, description: str = ""):
        """Aggiorna progresso"""
        self.current_step += 1
        
        if description:
            self.step_descriptions[self.current_step] = description
        
        self.step_times.append(datetime.now())
        
        progress_percent = (self.current_step / self.total_steps) * 100
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        # Stima tempo rimanente
        if self.current_step > 0:
            avg_step_time = elapsed / self.current_step
            remaining_steps = self.total_steps - self.current_step
            eta = remaining_steps * avg_step_time
            eta_str = f" (ETA: {int(eta//60)}m {int(eta%60)}s)" if eta > 0 else ""
        else:
            eta_str = ""
        
        logger.info(f"Progresso: {progress_percent:.1f}% - {description}{eta_str}")
        
        return {
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'progress_percent': progress_percent,
            'description': description,
            'elapsed_seconds': elapsed,
            'eta_str': eta_str
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Ottieni riassunto completo del progresso"""
        total_time = (datetime.now() - self.start_time).total_seconds()
        
        return {
            'total_steps': self.total_steps,
            'completed_steps': self.current_step,
            'total_time_seconds': total_time,
            'average_step_time': total_time / max(1, self.current_step),
            'step_descriptions': self.step_descriptions,
            'success_rate': (self.current_step / self.total_steps) * 100
        }

class DataExporter:
    """Export dati in vari formati"""
    
    @staticmethod
    def to_excel(data: Dict[str, Any], filename: str) -> str:
        """Esporta in Excel (richiede openpyxl)"""
        try:
            import pandas as pd
            
            # Crea DataFrame per ogni sezione
            sheets = {}
            
            # Executive Summary
            if 'final_report' in data:
                summary_data = {'Report': [data['final_report']]}
                sheets['Executive_Summary'] = pd.DataFrame(summary_data)
            
            # SEO Data
            if 'semrush' in data.get('analysis_results', {}):
                seo_data = data['analysis_results']['semrush']
                if isinstance(seo_data, dict):
                    sheets['SEO_Analysis'] = pd.DataFrame([seo_data])
            
            # Competitor Data
            if 'competitors' in data.get('analysis_results', {}):
                comp_data = data['analysis_results']['competitors']
                if 'competitor_analysis' in comp_data and 'competitors' in comp_data['competitor_analysis']:
                    competitors = comp_data['competitor_analysis']['competitors']
                    if isinstance(competitors, list):
                        sheets['Competitors'] = pd.DataFrame(competitors)
            
            # Salva Excel
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                for sheet_name, df in sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            return filename
            
        except ImportError:
            logger.error("pandas e openpyxl richiesti per export Excel")
            return None
        except Exception as e:
            logger.error(f"Errore export Excel: {e}")
            return None
    
    @staticmethod
    def to_json(data: Dict[str, Any], filename: str, pretty: bool = True) -> str:
        """Esporta in JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                if pretty:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    json.dump(data, f, ensure_ascii=False)
            
            return filename
        except Exception as e:
            logger.error(f"Errore export JSON: {e}")
            return None
    
    @staticmethod
    def to_csv(data: Dict[str, Any], filename: str) -> str:
        """Esporta dati tabulari in CSV"""
        try:
            import pandas as pd
            
            # Estrai dati tabulari
            tabular_data = []
            
            # Aggiungi dati base
            tabular_data.append({
                'Metric': 'Company Name',
                'Value': data.get('company_name', 'N/A'),
                'Category': 'Basic Info'
            })
            
            tabular_data.append({
                'Metric': 'Website',
                'Value': data.get('website', 'N/A'),
                'Category': 'Basic Info'
            })
            
            # Aggiungi metriche SEO se disponibili
            semrush_data = data.get('analysis_results', {}).get('semrush', {}).get('analysis', {})
            for key, value in semrush_data.items():
                tabular_data.append({
                    'Metric': key,
                    'Value': str(value),
                    'Category': 'SEO'
                })
            
            df = pd.DataFrame(tabular_data)
            df.to_csv(filename, index=False, encoding='utf-8')
            
            return filename
        except Exception as e:
            logger.error(f"Errore export CSV: {e}")
            return None

# Utility functions standalone
def calculate_growth_rate(current: float, previous: float) -> float:
    """Calcola tasso di crescita percentuale"""
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100

def extract_domain_from_url(url: str) -> str:
    """Estrae dominio pulito da URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        # Rimuovi www.
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception:
        return ""

def format_timespan(start_date: datetime, end_date: datetime = None) -> str:
    """Formatta intervallo temporale"""
    if end_date is None:
        end_date = datetime.now()
    
    delta = end_date - start_date
    
    if delta.days > 365:
        years = delta.days // 365
        return f"{years} ann{'o' if years == 1 else 'i'}"
    elif delta.days > 30:
        months = delta.days // 30
        return f"{months} mes{'e' if months == 1 else 'i'}"
    elif delta.days > 0:
        return f"{delta.days} giorn{'o' if delta.days == 1 else 'i'}"
    else:
        hours = delta.seconds // 3600
        return f"{hours} or{'a' if hours == 1 else 'e'}"

def generate_report_filename(company_name: str, report_type: str = "business_analysis") -> str:
    """Genera nome file per report"""
    # Pulisci nome azienda
    clean_name = re.sub(r'[^\w\s-]', '', company_name)
    clean_name = re.sub(r'\s+', '_', clean_name).lower()
    
    # Aggiungi timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    
    return f"{report_type}_{clean_name}_{timestamp}"
