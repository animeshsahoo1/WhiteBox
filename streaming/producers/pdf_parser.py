import os
import time
import json
import re
import requests
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()


class PDFParser:
    """Parse PDFs to JSONL chunks using LandingAI ADE with Unstructured fallback"""
    
    def __init__(self):
        self.knowledge_base = Path(os.getenv('KNOWLEDGE_BASE_DIR', '../knowledge_base')).resolve()
        self.unstructured_api_key = os.getenv('UNSTRUCTURED_API_KEY')
        
        # Try to initialize LandingAI client
        try:
            from landingai_ade import LandingAIADE
            self.landingai_client = LandingAIADE()
            print(f"✓ LandingAI ADE initialized")
        except ImportError:
            self.landingai_client = None
            print(f"⚠️ LandingAI ADE not available, will use Unstructured fallback")
        
        if self.unstructured_api_key:
            print(f"✓ Unstructured API key found (fallback ready)")
        else:
            print(f"⚠️ No UNSTRUCTURED_API_KEY set (fallback not available)")
        
        print(f"📂 Knowledge base: {self.knowledge_base}")
    
    @staticmethod
    def normalize(markdown: str) -> str:
        """Remove HTML tags and normalize whitespace"""
        text = re.sub(r"<[^>]+>", "", markdown)
        text = text.replace("\n\n", "\n").strip()
        return text
    
    def _unstructured_request(
        self,
        contents: bytes,
        strategy: str = "hi_res",
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> Optional[requests.Response]:
        """Send request to Unstructured API with retry logic."""
        api_url = "https://api.unstructuredapp.io/general/v0/general"
        headers = {
            "accept": "application/json",
            "unstructured-api-key": self.unstructured_api_key,
        }
        files = {"files": contents}
        data = {"strategy": strategy}

        for attempt in range(max_retries):
            try:
                response = requests.post(api_url, headers=headers, files=files, data=data)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                print(f"⚠️ Unstructured attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    return None
        return None
    
    def parse_pdf_with_unstructured(self, pdf_path: Path) -> List[Dict]:
        """Parse a PDF file using Unstructured API (fallback)."""
        if not self.unstructured_api_key:
            print(f"❌ UNSTRUCTURED_API_KEY not set, cannot use fallback")
            return []
        
        try:
            print(f"📄 Parsing with Unstructured (fallback): {pdf_path.name}")
            
            with open(pdf_path, "rb") as f:
                contents = f.read()
            
            response = self._unstructured_request(contents)
            
            if response is None:
                print(f"❌ Unstructured API request failed for {pdf_path.name}")
                return []
            
            try:
                elements = response.json()
            except:
                elements = eval(response.text)
            
            chunks = []
            for idx, element in enumerate(elements):
                text = element.get("text", "")
                if not text.strip():
                    continue
                
                chunks.append({
                    "id": element.get("element_id", f"chunk_{idx}"),
                    "page": element.get("metadata", {}).get("page_number", 0),
                    "type": element.get("type", "unknown"),
                    "bbox": {},  # Unstructured doesn't always provide bbox
                    "text": self.normalize(text)
                })
            
            print(f"✓ Extracted {len(chunks)} chunks from {pdf_path.name} (Unstructured)")
            return chunks
            
        except Exception as e:
            print(f"❌ Unstructured error for {pdf_path.name}: {e}")
            return []
    
    def parse_pdf_with_landingai(self, pdf_path: Path) -> List[Dict]:
        """Parse a PDF file using LandingAI ADE (primary)."""
        if not self.landingai_client:
            return []
        
        try:
            print(f"📄 Parsing with LandingAI: {pdf_path.name}")
            
            response = self.landingai_client.parse(
                document=pdf_path,
                model="dpt-2-latest"
            )
            
            chunks = []
            for ch in response.chunks:
                chunks.append({
                    "id": ch.id,
                    "page": ch.grounding.page,
                    "type": ch.type,
                    "bbox": ch.grounding.box.__dict__,
                    "text": self.normalize(ch.markdown)
                })
            
            print(f"✓ Extracted {len(chunks)} chunks from {pdf_path.name} (LandingAI)")
            return chunks
            
        except Exception as e:
            print(f"❌ LandingAI error for {pdf_path.name}: {e}")
            return []
    
    def parse_pdf(self, pdf_path: Path) -> List[Dict]:
        """Parse a single PDF file with fallback support."""
        # Try LandingAI first (primary)
        if self.landingai_client:
            chunks = self.parse_pdf_with_landingai(pdf_path)
            if chunks:
                return chunks
            print(f"⚠️ LandingAI failed, trying Unstructured fallback...")
        
        # Fallback to Unstructured
        if self.unstructured_api_key:
            chunks = self.parse_pdf_with_unstructured(pdf_path)
            if chunks:
                return chunks
        
        print(f"❌ All parsers failed for {pdf_path.name}")
        return []
    
    def save_chunks(self, chunks: List[Dict], output_path: Path):
        """Save chunks to JSONL file"""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for chunk in chunks:
                    f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
            
            print(f"✅ Saved {len(chunks)} chunks to {output_path.name}")
            
        except Exception as e:
            print(f"❌ Error saving chunks: {e}")
    
    def parse_stock_pdfs(self, stock_symbol: str):
        """Parse all PDFs for a stock symbol"""
        stock_dir = self.knowledge_base / stock_symbol
        
        if not stock_dir.exists():
            print(f"⚠️ Directory not found: {stock_dir}")
            return
        
        # Get all PDF files
        pdf_files = list(stock_dir.glob("*.pdf"))
        
        if not pdf_files:
            print(f"⚠️ No PDF files found in {stock_dir}")
            return
        
        print(f"\n📚 Found {len(pdf_files)} PDF files for {stock_symbol}")
        
        # Create jsons output directory
        jsons_dir = stock_dir / "jsons"
        jsons_dir.mkdir(exist_ok=True)
        
        # Parse each PDF
        for pdf_path in pdf_files:
            # Create output filename
            output_name = f"parsed_chunks_{pdf_path.stem}.jsonl"
            output_path = jsons_dir / output_name
            
            # Skip if already parsed
            if output_path.exists():
                print(f"⏭️  Skipping {pdf_path.name} (already parsed)")
                continue
            
            # Parse and save
            chunks = self.parse_pdf(pdf_path)
            if chunks:
                self.save_chunks(chunks, output_path)
            
            # Rate limiting
            time.sleep(1)
    
    def parse_all_stocks(self):
        """Parse PDFs for all stocks in knowledge base"""
        if not self.knowledge_base.exists():
            print(f"❌ Knowledge base directory not found: {self.knowledge_base}")
            return
        
        # Get all stock directories
        stock_dirs = [d for d in self.knowledge_base.iterdir() if d.is_dir()]
        
        if not stock_dirs:
            print(f"⚠️ No stock directories found in {self.knowledge_base}")
            return
        
        print(f"\n{'='*70}")
        print(f"PDF Parser - Processing {len(stock_dirs)} stocks")
        print(f"{'='*70}\n")
        
        for stock_dir in stock_dirs:
            try:
                self.parse_stock_pdfs(stock_dir.name)
                time.sleep(2)
            except Exception as e:
                print(f"❌ Error processing {stock_dir.name}: {e}")
        
        print(f"\n{'='*70}")
        print("✅ PDF parsing complete")
        print(f"{'='*70}\n")


def main():
    parser = PDFParser()
    parser.parse_all_stocks()


if __name__ == '__main__':
    main()
