import os
import time
import json
import re
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
from landingai_ade import LandingAIADE

load_dotenv()


class PDFParser:
    """Parse PDFs to JSONL chunks using LandingAI ADE"""
    
    def __init__(self):
        self.client = LandingAIADE()
        self.knowledge_base = Path(os.getenv('KNOWLEDGE_BASE_DIR', '../knowledge_base')).resolve()
        print(f"📂 Knowledge base: {self.knowledge_base}")
    
    @staticmethod
    def normalize(markdown: str) -> str:
        """Remove HTML tags and normalize whitespace"""
        text = re.sub(r"<[^>]+>", "", markdown)
        text = text.replace("\n\n", "\n").strip()
        return text
    
    def parse_pdf(self, pdf_path: Path) -> List[Dict]:
        """Parse a single PDF file and return chunks"""
        try:
            print(f"📄 Parsing: {pdf_path.name}")
            
            response = self.client.parse(
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
            
            print(f"✓ Extracted {len(chunks)} chunks from {pdf_path.name}")
            return chunks
            
        except Exception as e:
            print(f"❌ Error parsing {pdf_path.name}: {e}")
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
