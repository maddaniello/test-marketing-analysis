# Configuration file for Business Intelligence Analyzer
import os
from typing import Dict, List

class Config:
    """Configurazione centrale dell'applicazione"""
    
    # API Endpoints
    SEMRUSH_API_BASE = "https://api.semrush.com/"
    SERPER_API_BASE = "https://google.serper.dev/"
    OPENAI_API_BASE = "https://api.openai.com/v1/"
    
    # Rate limiting (requests per minute)
    SEMRUSH_RATE_LIMIT = 10
    SERPER_RATE_LIMIT = 100
    OPENAI_RATE_LIMIT = 50
    
    # Timeout settings (seconds)
    API_TIMEOUT = 30
    ANALYSIS_TIMEOUT = 300
    
    # SEMRush specific configurations
    SEMRUSH_DISPLAY_LIMIT = 50
    SEMRUSH_EXPORT_COLUMNS = {
        'organic': 'Dn,Cr,Np,Or,Ot,Oc,Ad,At,Ac',
        'backlinks': 'target_url,source_url,anchor,last_seen',
        'competitors': 'Dn,Cr,Np,Or'
    }
    
    # Serper search configurations
    SERPER_SEARCH_PARAMS = {
        'gl': 'it',  # Geolocation: Italy
        'hl': 'it',  # Language: Italian
        'num': 20,   # Number of results
        'type': 'search'
    }
    
    # Social media platforms to analyze
    SOCIAL_PLATFORMS = [
        'instagram',
        'facebook', 
        'linkedin',
        'youtube',
        'tiktok',
        'twitter'
    ]
    
    # Financial data sources
    FINANCIAL_SOURCES = [
        'https://www.registroimprese.it/',
        'https://www.ufficiocamerale.it/',
        'https://www.reportaziende.it/',
        'https://www.aida.bvdinfo.com/'
    ]
    
    # OpenAI model configurations
    OPENAI_MODELS = {
        'analysis': 'gpt-4',
        'summary': 'gpt-3.5-turbo',
        'extraction': 'gpt-3.5-turbo'
    }
    
    # Report templates
    REPORT_SECTIONS = [
        'executive_summary',
        'company_profile', 
        'financial_analysis',
        'digital_presence',
        'competitor_analysis',
        'social_media',
        'swot_analysis',
        'recommendations',
        'conclusions'
    ]
    
    # Data validation rules
    VALIDATION_RULES = {
        'partita_iva': r'^\d{11}$',
        'codice_fiscale': r'^[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]$',
        'domain': r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$',
        'url': r'^https?://'
    }
    
    @classmethod
    def get_api_key(cls, service: str) -> str:
        """Recupera chiave API da variabili ambiente"""
        env_vars = {
            'openai': 'OPENAI_API_KEY',
            'semrush': 'SEMRUSH_API_KEY', 
            'serper': 'SERPER_API_KEY'
        }
        
        return os.getenv(env_vars.get(service, ''), '')
    
    @classmethod
    def validate_input(cls, input_type: str, value: str) -> bool:
        """Valida input secondo le regole definite"""
        import re
        
        if input_type not in cls.VALIDATION_RULES:
            return False
        
        pattern = cls.VALIDATION_RULES[input_type]
        return bool(re.match(pattern, value))
    
    @classmethod
    def get_search_queries(cls, company_name: str, sector: str = "") -> List[str]:
        """Genera query di ricerca ottimizzate"""
        base_queries = [
            f'"{company_name}" azienda',
            f'{company_name} competitor',
            f'{company_name} alternative',
            f'{company_name} simili'
        ]
        
        if sector:
            sector_queries = [
                f'{sector} aziende Italia',
                f'{sector} leader mercato italiano',
                f'migliori {sector} Italia'
            ]
            base_queries.extend(sector_queries)
        
        return base_queries
    
    @classmethod
    def get_semrush_params(cls, domain: str, report_type: str) -> Dict[str, str]:
        """Genera parametri per API SEMRush"""
        base_params = {
            'key': cls.get_api_key('semrush'),
            'domain': domain,
            'display_limit': str(cls.SEMRUSH_DISPLAY_LIMIT),
            'database': 'it'  # Database italiano
        }
        
        type_configs = {
            'organic': {
                'type': 'domain_organic',
                'export_columns': cls.SEMRUSH_EXPORT_COLUMNS['organic']
            },
            'backlinks': {
                'type': 'backlinks_overview',
                'export_columns': cls.SEMRUSH_EXPORT_COLUMNS['backlinks']
            },
            'competitors': {
                'type': 'domain_organic_organic',
                'export_columns': cls.SEMRUSH_EXPORT_COLUMNS['competitors']
            },
            'paid': {
                'type': 'domain_adwords',
                'export_columns': 'Dn,Cr,Np,Ad,At,Ac'
            }
        }
        
        if report_type in type_configs:
            base_params.update(type_configs[report_type])
        
        return base_params

class PromptTemplates:
    """Template per prompt AI ottimizzati"""
    
    SEMRUSH_ANALYZER = """
    Sei un esperto analista SEO e digital marketing. Analizza i seguenti dati SEMRush e fornisci insights strutturati.
    
    DATI DA ANALIZZARE:
    {data}
    
    FORNISCI UN'ANALISI STRUTTURATA CHE INCLUDA:
    1. Panoramica performance SEO (traffico, keyword, visibilità)
    2. Analisi backlink profile (qualità, diversità, opportunità)
    3. Competitor landscape (chi sono, punti di forza/debolezza)
    4. Gap analysis e opportunità di crescita
    5. Raccomandazioni actionable prioritizzate
    
    Formato output: JSON strutturato con sezioni chiare e metriche quantificate.
    """
    
    COMPETITOR_ANALYZER = """
    Sei un esperto di competitive intelligence. Analizza i risultati di ricerca per identificare e profilare i competitor.
    
    RISULTATI RICERCA:
    {data}
    
    PER OGNI COMPETITOR IDENTIFICATO, ESTRAI:
    1. Nome azienda e ragione sociale
    2. Sito web e presenza digitale
    3. Proposta di valore principale
    4. Prodotti/servizi chiave
    5. Mercato geografico di riferimento
    6. Dimensione stimata (se deducibile)
    7. Punti di forza distintivi
    
    Formato output: JSON con array di competitor ordinati per rilevanza/dimensione.
    """
    
    SOCIAL_ANALYZER = """
    Sei un esperto di social media marketing e analytics. Analizza la presenza social dell'azienda.
    
    DATI SOCIAL:
    {data}
    
    ANALIZZA E FORNISCI:
    1. Panoramica presence su ogni piattaforma
    2. Metriche di engagement e performance
    3. Tipologia e qualità dei contenuti
    4. Frequenza di pubblicazione
    5. Audience analysis (quando possibile)
    6. Benchmark vs competitor (se disponibili)
    7. Raccomandazioni per miglioramento
    
    Formato output: JSON strutturato per piattaforma con KPI e insights.
    """
    
    FINANCIAL_ANALYZER = """
    Sei un analista finanziario esperto in valutazione aziendale. Analizza i dati finanziari forniti.
    
    DATI FINANZIARI:
    {data}
    
    CONDUCI ANALISI SU:
    1. Trend fatturato e crescita (%, CAGR)
    2. Solidità patrimoniale (ratios, leverage)
    3. Efficienza operativa (costi, margini)
    4. Dimensione organizzativa (dipendenti, produttività)
    5. Benchmark settoriale (quando possibile)
    6. Indicatori di salute finanziaria
    7. Proiezioni e raccomandazioni
    
    Formato output: JSON con sezioni finanziarie e assessment qualitativo.
    """
    
    REPORT_GENERATOR = """
    Sei un consulente senior di business intelligence. Crea un report esecutivo completo e professionale.
    
    DATI COMPLETI RACCOLTI:
    {data}
    
    STRUTTURA IL REPORT CON:
    1. EXECUTIVE SUMMARY (3-4 bullet point chiave)
    2. PROFILO AZIENDALE (overview strutturata)
    3. ANALISI PERFORMANCE DIGITALE (SEO, social, web)
    4. COMPETITIVE LANDSCAPE (competitor mapping)
    5. ANALISI FINANZIARIA (trend, KPI, solidità)
    6. SWOT ANALYSIS (strutturata e bilanciata)
    7. RACCOMANDAZIONI STRATEGICHE (actionable, prioritizzate)
    8. CONCLUSIONI E NEXT STEPS
    
    Il report deve essere:
    - Professionale e ben strutturato
    - Orientato all'azione e al business
    - Supportato da dati quantitativi
    - Comprensibile per executive non tecnici
    
    Formato output: Markdown professionale pronto per presentazione.
    """
    
    @classmethod
    def get_prompt(cls, prompt_type: str, data: str, context: str = "") -> str:
        """Genera prompt specifico con dati"""
        templates = {
            'semrush': cls.SEMRUSH_ANALYZER,
            'competitor': cls.COMPETITOR_ANALYZER,
            'social': cls.SOCIAL_ANALYZER,
            'financial': cls.FINANCIAL_ANALYZER,
            'report': cls.REPORT_GENERATOR
        }
        
        if prompt_type not in templates:
            return f"Analizza i seguenti dati: {data}"
        
        prompt = templates[prompt_type].format(data=data)
        
        if context:
            prompt += f"\n\nCONTESTO AGGIUNTIVO:\n{context}"
        
        return prompt

class ErrorMessages:
    """Messaggi di errore standardizzati"""
    
    API_KEY_MISSING = "Chiave API mancante per {service}"
    API_RATE_LIMIT = "Rate limit raggiunto per {service}. Riprova tra {seconds} secondi"
    API_TIMEOUT = "Timeout durante chiamata API a {service}"
    API_ERROR = "Errore API {service}: {message}"
    
    INVALID_INPUT = "Input non valido: {input_type}"
    COMPANY_NOT_FOUND = "Azienda non trovata: {company_name}"
    NO_DATA_AVAILABLE = "Nessun dato disponibile per {data_type}"
    
    ANALYSIS_FAILED = "Analisi fallita: {reason}"
    REPORT_GENERATION_FAILED = "Errore generazione report: {reason}"
    
    @classmethod
    def format_error(cls, error_type: str, **kwargs) -> str:
        """Formatta messaggio di errore"""
        if hasattr(cls, error_type):
            template = getattr(cls, error_type)
            return template.format(**kwargs)
        return f"Errore sconosciuto: {error_type}"
