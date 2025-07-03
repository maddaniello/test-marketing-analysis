# Business Intelligence Analyzer
# Applicativo per analisi preliminari di marketing/digital marketing
# Utilizza multiple AI agents per raccogliere dati completi sulle aziende

import streamlit as st
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dataclasses import dataclass, asdict
import requests
import time
import re
from urllib.parse import urlparse
import logging

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CompanyData:
    """Struttura dati per le informazioni aziendali"""
    # Profilo aziendale
    nome_azienda: str = ""
    partita_iva: str = ""
    sede_legale: str = ""
    anno_fondazione: str = ""
    settore: str = ""
    descrizione: str = ""
    
    # Dati finanziari
    fatturato_anni: Dict[str, float] = None
    patrimonio_netto: float = 0
    capitale_sociale: float = 0
    totale_attivo: float = 0
    dipendenti: int = 0
    
    # Presenza digitale
    sito_web: str = ""
    traffico_organico: int = 0
    keywords_organiche: int = 0
    backlinks: int = 0
    domini_referenti: int = 0
    
    # Social media
    social_profiles: Dict[str, Dict] = None
    
    # Competitors
    competitors: List[str] = None
    
    def __post_init__(self):
        if self.fatturato_anni is None:
            self.fatturato_anni = {}
        if self.social_profiles is None:
            self.social_profiles = {}
        if self.competitors is None:
            self.competitors = []

class OpenAIAgent:
    """Classe base per gli agenti AI"""
    
    def __init__(self, api_key: str, role: str, instructions: str):
        self.api_key = api_key
        self.role = role
        self.instructions = instructions
        self.client = None
        
    def setup_client(self):
        """Configura il client OpenAI"""
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key)
            return True
        except Exception as e:
            logger.error(f"Errore configurazione OpenAI: {e}")
            return False
    
    async def analyze(self, data: str, context: str = "") -> Dict[str, Any]:
        """Analizza i dati utilizzando OpenAI"""
        if not self.client:
            if not self.setup_client():
                return {"error": "Impossibile configurare OpenAI client"}
        
        try:
            prompt = f"""
            {self.instructions}
            
            Contesto: {context}
            
            Dati da analizzare:
            {data}
            
            Fornisci una risposta strutturata in formato JSON.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.role},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            result = response.choices[0].message.content
            
            # Prova a parsare come JSON
            try:
                return json.loads(result)
            except:
                return {"raw_response": result}
                
        except Exception as e:
            logger.error(f"Errore analisi OpenAI: {e}")
            return {"error": str(e)}

class SEMRushAgent(OpenAIAgent):
    """Agente specializzato per analisi SEMRush"""
    
    def __init__(self, api_key: str, semrush_api_key: str):
        super().__init__(
            api_key=api_key,
            role="Sei un esperto analista SEO e digital marketing specializzato nell'interpretazione di dati SEMRush.",
            instructions="""
            Analizza i dati SEMRush forniti e estrai:
            1. Traffico organico e keyword posizionate
            2. Backlinks e domini referenti
            3. Competitor principali
            4. Trend di crescita/decrescita
            5. Opportunità SEO identificate
            
            Struttura la risposta in JSON con le seguenti chiavi:
            - traffico_organico
            - keywords_organiche
            - backlinks
            - domini_referenti
            - competitors
            - trend_analisi
            - raccomandazioni
            """
        )
        self.semrush_api_key = semrush_api_key
    
    def get_domain_from_input(self, user_input: str) -> str:
        """Estrae il dominio dall'input utente"""
        # Se è già un URL
        if user_input.startswith(('http://', 'https://')):
            return urlparse(user_input).netloc
        
        # Se contiene un punto, probabilmente è un dominio
        if '.' in user_input and ' ' not in user_input:
            return user_input.replace('www.', '')
        
        return None
    
    async def fetch_semrush_data(self, domain: str) -> Dict[str, Any]:
        """Recupera dati da SEMRush API"""
        if not domain:
            return {"error": "Dominio non valido"}
        
        semrush_data = {}
        base_url = "https://api.semrush.com/"
        
        # Parametri base
        params = {
            "type": "domain_organic",
            "key": self.semrush_api_key,
            "display_limit": 50,
            "export_columns": "Dn,Cr,Np,Or,Ot,Oc,Ad,At,Ac",
            "domain": domain
        }
        
        try:
            # 1. Dati organici
            response = requests.get(base_url, params=params, timeout=30)
            if response.status_code == 200:
                organic_data = response.text
                semrush_data["organic"] = organic_data
            
            # 2. Backlinks
            params["type"] = "backlinks_overview"
            response = requests.get(base_url, params=params, timeout=30)
            if response.status_code == 200:
                backlinks_data = response.text
                semrush_data["backlinks"] = backlinks_data
            
            # 3. Competitor
            params["type"] = "domain_organic_organic"
            params["display_limit"] = 20
            response = requests.get(base_url, params=params, timeout=30)
            if response.status_code == 200:
                competitors_data = response.text
                semrush_data["competitors"] = competitors_data
            
            return semrush_data
            
        except Exception as e:
            logger.error(f"Errore recupero dati SEMRush: {e}")
            return {"error": str(e)}
    
    async def analyze_company(self, user_input: str) -> Dict[str, Any]:
        """Analizza un'azienda utilizzando SEMRush"""
        domain = self.get_domain_from_input(user_input)
        
        if not domain:
            return {"error": "Impossibile determinare il dominio dall'input fornito"}
        
        # Recupera dati SEMRush
        semrush_data = await self.fetch_semrush_data(domain)
        
        if "error" in semrush_data:
            return semrush_data
        
        # Analizza con OpenAI
        context = f"Analisi SEMRush per il dominio: {domain}"
        analysis = await self.analyze(json.dumps(semrush_data), context)
        
        return {
            "domain": domain,
            "semrush_raw": semrush_data,
            "analysis": analysis
        }

class SerperAgent(OpenAIAgent):
    """Agente per ricerca competitor con Serper.dev"""
    
    def __init__(self, api_key: str, serper_api_key: str):
        super().__init__(
            api_key=api_key,
            role="Sei un esperto ricercatore di mercato specializzato nell'identificazione e analisi di competitor.",
            instructions="""
            Analizza i risultati di ricerca per identificare competitor e raccogliere informazioni su:
            1. Nome azienda e ragione sociale
            2. Sito web principale
            3. Servizi e prodotti principali
            4. Presenza geografica
            5. Informazioni di contatto disponibili
            
            Struttura la risposta in JSON con array di competitor, ognuno con:
            - nome_azienda
            - sito_web
            - descrizione_business
            - servizi_principali
            - area_geografica
            """
        )
        self.serper_api_key = serper_api_key
    
    async def search_competitors(self, company_name: str, sector: str = "") -> Dict[str, Any]:
        """Cerca competitor utilizzando Serper.dev"""
        
        search_queries = [
            f"{company_name} competitor",
            f"{company_name} alternative",
            f"{sector} aziende italiane" if sector else f"{company_name} simili aziende"
        ]
        
        all_results = []
        
        for query in search_queries:
            try:
                url = "https://google.serper.dev/search"
                payload = json.dumps({
                    "q": query,
                    "gl": "it",
                    "hl": "it",
                    "num": 20
                })
                headers = {
                    'X-API-KEY': self.serper_api_key,
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(url, headers=headers, data=payload, timeout=30)
                
                if response.status_code == 200:
                    results = response.json()
                    all_results.append({
                        "query": query,
                        "results": results
                    })
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Errore ricerca Serper: {e}")
        
        # Analizza risultati con OpenAI
        context = f"Ricerca competitor per: {company_name}"
        analysis = await self.analyze(json.dumps(all_results), context)
        
        return {
            "search_results": all_results,
            "competitor_analysis": analysis
        }

class SocialMediaAgent(OpenAIAgent):
    """Agente per analisi social media"""
    
    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            role="Sei un esperto analista di social media marketing.",
            instructions="""
            Analizza i dati dei social media e estrai:
            1. Follower/fan count per piattaforma
            2. Engagement rate medio
            3. Frequenza di posting
            4. Tipo di contenuti pubblicati
            5. Performance dei post più popolari
            
            Struttura la risposta in JSON per ogni piattaforma:
            - platform
            - follower_count
            - engagement_rate
            - posting_frequency
            - content_types
            - performance_insights
            """
        )
    
    async def find_social_profiles(self, company_name: str, website: str = "") -> Dict[str, Any]:
        """Trova e analizza profili social dell'azienda"""
        
        # Implementazione semplificata - in produzione si potrebbero usare API specifiche
        platforms = ["instagram", "facebook", "linkedin", "youtube", "tiktok"]
        social_data = {}
        
        for platform in platforms:
            # Simula ricerca profili social
            # In produzione, implementare ricerca via Serper o API specifiche
            profile_data = await self._search_platform_profile(company_name, platform, website)
            if profile_data:
                social_data[platform] = profile_data
        
        # Analizza con OpenAI
        context = f"Analisi profili social per: {company_name}"
        analysis = await self.analyze(json.dumps(social_data), context)
        
        return {
            "social_profiles": social_data,
            "social_analysis": analysis
        }
    
    async def _search_platform_profile(self, company_name: str, platform: str, website: str) -> Dict[str, Any]:
        """Cerca profilo specifico su una piattaforma"""
        # Implementazione placeholder
        # In produzione, implementare ricerca effettiva
        return {
            "platform": platform,
            "profile_url": f"https://{platform}.com/{company_name.lower().replace(' ', '')}",
            "found": False,
            "followers": 0,
            "posts": 0
        }

class FinancialAgent(OpenAIAgent):
    """Agente per analisi dati finanziari"""
    
    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            role="Sei un esperto analista finanziario specializzato nell'interpretazione di bilanci aziendali.",
            instructions="""
            Analizza i dati finanziari e societari per estrarre:
            1. Fatturato degli ultimi anni disponibili
            2. Crescita anno su anno (%)
            3. Patrimonio netto e capitale sociale
            4. Numero dipendenti e costo del personale
            5. Indicatori di solidità finanziaria
            
            Struttura la risposta in JSON con:
            - fatturato_evolution
            - growth_rates
            - financial_indicators
            - employee_data
            - financial_health_assessment
            """
        )
    
    async def analyze_financial_data(self, partita_iva: str, company_name: str) -> Dict[str, Any]:
        """Analizza dati finanziari dell'azienda"""
        
        # Implementazione per ricerca su siti di informazioni aziendali
        financial_data = await self._search_company_financials(partita_iva, company_name)
        
        # Analizza con OpenAI
        context = f"Analisi finanziaria per: {company_name} (P.IVA: {partita_iva})"
        analysis = await self.analyze(json.dumps(financial_data), context)
        
        return {
            "financial_raw_data": financial_data,
            "financial_analysis": analysis
        }
    
    async def _search_company_financials(self, partita_iva: str, company_name: str) -> Dict[str, Any]:
        """Cerca dati finanziari sui siti di informazioni aziendali"""
        # Implementazione placeholder per ricerca su:
        # - registroimprese.it
        # - ufficiocamerale.it  
        # - reportaziende.it
        
        return {
            "source": "Ricerca automatica dati finanziari",
            "partita_iva": partita_iva,
            "company_name": company_name,
            "data_found": False,
            "financial_data": {}
        }

class ReportAgent(OpenAIAgent):
    """Agente per generazione report finale"""
    
    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            role="Sei un esperto consulente di business intelligence e marketing strategico.",
            instructions="""
            Crea un report completo e professionale che includa:
            1. Executive Summary con key insights
            2. Analisi dettagliata per ogni sezione
            3. Analisi SWOT
            4. Raccomandazioni strategiche actionable
            5. Conclusioni e next steps
            
            Il report deve essere strutturato, professionale e orientato all'azione.
            """
        )
    
    async def generate_comprehensive_report(self, all_data: Dict[str, Any]) -> str:
        """Genera report comprensivo basato su tutti i dati raccolti"""
        
        context = "Generazione report business intelligence completo"
        report_data = json.dumps(all_data, indent=2, ensure_ascii=False)
        
        analysis = await self.analyze(report_data, context)
        
        # Genera report strutturato
        report = self._format_report(analysis, all_data)
        
        return report
    
    def _format_report(self, analysis: Dict[str, Any], raw_data: Dict[str, Any]) -> str:
        """Formatta il report finale"""
        
        current_date = datetime.now().strftime("%d/%m/%Y")
        
        report = f"""
# BUSINESS INTELLIGENCE REPORT
## Data di generazione: {current_date}

### EXECUTIVE SUMMARY

{analysis.get('executive_summary', 'Analisi completa dei dati aziendali raccolti.')}

### 1. PROFILO AZIENDALE

**Nome Azienda:** {raw_data.get('company_name', 'N/A')}
**Sito Web:** {raw_data.get('website', 'N/A')}
**Settore:** {analysis.get('sector', 'N/A')}

### 2. ANALISI DIGITALE E SEO

{self._format_seo_section(raw_data.get('semrush_data', {}))}

### 3. ANALISI COMPETITOR

{self._format_competitor_section(raw_data.get('competitor_data', {}))}

### 4. PRESENZA SOCIAL MEDIA

{self._format_social_section(raw_data.get('social_data', {}))}

### 5. DATI FINANZIARI

{self._format_financial_section(raw_data.get('financial_data', {}))}

### 6. ANALISI SWOT

{analysis.get('swot_analysis', 'Analisi SWOT da completare con dati aggiuntivi.')}

### 7. RACCOMANDAZIONI STRATEGICHE

{analysis.get('strategic_recommendations', 'Raccomandazioni da definire in base ai risultati dell\'analisi.')}

### 8. CONCLUSIONI

{analysis.get('conclusions', 'Report generato automaticamente dal sistema di Business Intelligence.')}

---
*Report generato automaticamente da Business Intelligence Analyzer*
        """
        
        return report
    
    def _format_seo_section(self, seo_data: Dict) -> str:
        """Formatta sezione SEO"""
        if not seo_data:
            return "Dati SEO non disponibili."
        
        return f"""
**Traffico Organico:** {seo_data.get('organic_traffic', 'N/A')}
**Keywords Posizionate:** {seo_data.get('keywords', 'N/A')}
**Backlinks:** {seo_data.get('backlinks', 'N/A')}
**Domini Referenti:** {seo_data.get('referring_domains', 'N/A')}
        """
    
    def _format_competitor_section(self, competitor_data: Dict) -> str:
        """Formatta sezione competitor"""
        if not competitor_data:
            return "Analisi competitor non disponibile."
        
        competitors = competitor_data.get('competitors', [])
        if competitors:
            competitor_list = "\n".join([f"- {comp}" for comp in competitors[:5]])
            return f"**Principali Competitor Identificati:**\n{competitor_list}"
        
        return "Nessun competitor identificato."
    
    def _format_social_section(self, social_data: Dict) -> str:
        """Formatta sezione social media"""
        if not social_data:
            return "Dati social media non disponibili."
        
        social_summary = []
        for platform, data in social_data.items():
            if isinstance(data, dict) and data.get('found'):
                followers = data.get('followers', 0)
                social_summary.append(f"**{platform.title()}:** {followers} follower")
        
        return "\n".join(social_summary) if social_summary else "Profili social non identificati."
    
    def _format_financial_section(self, financial_data: Dict) -> str:
        """Formatta sezione finanziaria"""
        if not financial_data:
            return "Dati finanziari non disponibili."
        
        return "Ricerca dati finanziari in corso. Risultati disponibili con accesso a database aziendali."

class BusinessAnalyzer:
    """Classe principale per l'analisi business"""
    
    def __init__(self):
        self.openai_api_key = None
        self.semrush_api_key = None
        self.serper_api_key = None
        
        # Agenti AI
        self.semrush_agent = None
        self.serper_agent = None
        self.social_agent = None
        self.financial_agent = None
        self.report_agent = None
    
    def setup_agents(self, openai_key: str, semrush_key: str, serper_key: str):
        """Configura tutti gli agenti AI"""
        self.openai_api_key = openai_key
        self.semrush_api_key = semrush_key
        self.serper_api_key = serper_key
        
        # Inizializza agenti
        self.semrush_agent = SEMRushAgent(openai_key, semrush_key)
        self.serper_agent = SerperAgent(openai_key, serper_key)
        self.social_agent = SocialMediaAgent(openai_key)
        self.financial_agent = FinancialAgent(openai_key)
        self.report_agent = ReportAgent(openai_key)
    
    async def analyze_company(self, user_input: str, progress_callback=None) -> Dict[str, Any]:
        """Esegue analisi completa dell'azienda"""
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "input": user_input,
            "company_name": "",
            "website": "",
            "analysis_results": {}
        }
        
        try:
            # Step 1: Analisi SEMRush
            if progress_callback:
                progress_callback("Analisi SEO e traffico con SEMRush...")
            
            semrush_results = await self.semrush_agent.analyze_company(user_input)
            results["analysis_results"]["semrush"] = semrush_results
            
            # Estrai informazioni base
            if "domain" in semrush_results:
                results["website"] = semrush_results["domain"]
            
            # Step 2: Ricerca competitor
            if progress_callback:
                progress_callback("Ricerca competitor con Serper.dev...")
            
            company_name = self._extract_company_name(user_input)
            results["company_name"] = company_name
            
            competitor_results = await self.serper_agent.search_competitors(company_name)
            results["analysis_results"]["competitors"] = competitor_results
            
            # Step 3: Analisi social media
            if progress_callback:
                progress_callback("Analisi profili social media...")
            
            social_results = await self.social_agent.find_social_profiles(
                company_name, results["website"]
            )
            results["analysis_results"]["social"] = social_results
            
            # Step 4: Analisi finanziaria
            if progress_callback:
                progress_callback("Ricerca dati finanziari...")
            
            partita_iva = self._extract_partita_iva(user_input)
            financial_results = await self.financial_agent.analyze_financial_data(
                partita_iva, company_name
            )
            results["analysis_results"]["financial"] = financial_results
            
            # Step 5: Generazione report
            if progress_callback:
                progress_callback("Generazione report finale...")
            
            final_report = await self.report_agent.generate_comprehensive_report(results)
            results["final_report"] = final_report
            
            return results
            
        except Exception as e:
            logger.error(f"Errore durante analisi: {e}")
            results["error"] = str(e)
            return results
    
    def _extract_company_name(self, user_input: str) -> str:
        """Estrae nome azienda dall'input"""
        # Implementazione semplificata
        if user_input.startswith(('http://', 'https://')):
            domain = urlparse(user_input).netloc
            return domain.replace('www.', '').replace('.com', '').replace('.it', '')
        
        # Se contiene numeri, potrebbe essere P.IVA
        if re.search(r'\d{11}', user_input):
            return "Azienda da P.IVA"
        
        return user_input
    
    def _extract_partita_iva(self, user_input: str) -> str:
        """Estrae P.IVA dall'input se presente"""
        piva_match = re.search(r'\d{11}', user_input)
        return piva_match.group() if piva_match else ""

# Configurazione Streamlit
def setup_streamlit_page():
    """Configura la pagina Streamlit"""
    st.set_page_config(
        page_title="Business Intelligence Analyzer",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🔍 Business Intelligence Analyzer")
    st.markdown("""
    **Analisi preliminari complete per marketing e digital marketing**
    
    Questo strumento utilizza multiple AI agents per raccogliere e analizzare:
    - Dati SEO e traffico (SEMRush)
    - Competitor analysis (Serper.dev)
    - Profili social media
    - Dati finanziari aziendali
    """)

def main():
    """Funzione principale Streamlit"""
    setup_streamlit_page()
    
    # Sidebar per configurazione
    st.sidebar.header("🔑 Configurazione API")
    
    openai_key = st.sidebar.text_input(
        "OpenAI API Key", 
        type="password",
        help="Chiave API per OpenAI GPT-4"
    )
    
    semrush_key = st.sidebar.text_input(
        "SEMRush API Key", 
        type="password",
        help="Chiave API per SEMRush"
    )
    
    serper_key = st.sidebar.text_input(
        "Serper.dev API Key", 
        type="password",
        help="Chiave API per Serper.dev"
    )
    
    # Input principale
    st.header("📝 Inserisci i dati dell'azienda da analizzare")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        user_input = st.text_input(
            "Azienda da analizzare",
            placeholder="Es: Venezianico SRL, www.venezianico.com, 04427770278",
            help="Inserisci nome azienda, URL sito web o Partita IVA"
        )
    
    with col2:
        analyze_button = st.button(
            "🚀 Avvia Analisi",
            type="primary",
            disabled=not (openai_key and semrush_key and serper_key and user_input)
        )
    
    if analyze_button:
        if not all([openai_key, semrush_key, serper_key, user_input]):
            st.error("⚠️ Compila tutti i campi obbligatori")
            return
        
        # Inizializza analyzer
        analyzer = BusinessAnalyzer()
        analyzer.setup_agents(openai_key, semrush_key, serper_key)
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(message):
            status_text.text(f"🔄 {message}")
        
        # Esegui analisi
        with st.spinner("Analisi in corso..."):
            try:
                # Simula async in Streamlit
                import asyncio
                
                async def run_analysis():
                    return await analyzer.analyze_company(user_input, update_progress)
                
                # Esegui analisi asincrona
                results = asyncio.run(run_analysis())
                
                progress_bar.progress(100)
                status_text.text("✅ Analisi completata!")
                
                # Mostra risultati
                st.success("🎉 Analisi completata con successo!")
                
                # Tabs per risultati
                tab1, tab2, tab3, tab4 = st.tabs([
                    "📋 Report Finale", 
                    "📊 Dati SEO", 
                    "🏢 Competitor", 
                    "📱 Social Media"
                ])
                
                with tab1:
                    if "final_report" in results:
                        st.markdown(results["final_report"])
                        
                        # Download button per report
                        st.download_button(
                            label="📥 Scarica Report Completo",
                            data=results["final_report"],
                            file_name=f"business_report_{results['company_name']}_{datetime.now().strftime('%Y%m%d')}.md",
                            mime="text/markdown"
                        )
                    else:
                        st.error("Errore nella generazione del report")
                
                with tab2:
                    semrush_data = results.get("analysis_results", {}).get("semrush", {})
                    if semrush_data and "analysis" in semrush_data:
                        st.json(semrush_data["analysis"])
                    else:
                        st.info("Dati SEMRush non disponibili")
                
                with tab3:
                    competitor_data = results.get("analysis_results", {}).get("competitors", {})
                    if competitor_data and "competitor_analysis" in competitor_data:
                        st.json(competitor_data["competitor_analysis"])
                    else:
                        st.info("Dati competitor non disponibili")
                
                with tab4:
                    social_data = results.get("analysis_results", {}).get("social", {})
                    if social_data and "social_analysis" in social_data:
                        st.json(social_data["social_analysis"])
                    else:
                        st.info("Dati social media non disponibili")
                
                # Dati raw per debug (nascosti di default)
                with st.expander("🔍 Dati Raw (Debug)", expanded=False):
                    st.json(results)
                
            except Exception as e:
                progress_bar.progress(0)
                status_text.text("")
                st.error(f"❌ Errore durante l'analisi: {str(e)}")
                logger.error(f"Errore Streamlit: {e}")
    
    # Sezione informativa
    st.markdown("---")
    st.header("ℹ️ Come funziona")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **🔍 Analisi SEO**
        - Traffico organico
        - Keywords posizionate
        - Backlinks e autorità
        - Competitor SEO
        """)
    
    with col2:
        st.markdown("""
        **🏢 Ricerca Competitor**
        - Identificazione automatica
        - Analisi servizi/prodotti
        - Presenza geografica
        - Posizionamento mercato
        """)
    
    with col3:
        st.markdown("""
        **📱 Social & Finance**
        - Profili social media
        - Engagement e follower
        - Dati finanziari P.IVA
        - Report SWOT completo
        """)

if __name__ == "__main__":
    main()
