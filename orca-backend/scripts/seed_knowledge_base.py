"""Seed the curated knowledge base with real Indian marine regulations.

Loads the PDFs under data/knowledge/seed/ into the PostgreSQL knowledge base
via the standard ingestion pipeline (parse -> normalize -> metadata -> chunk
-> store).  Every entry carries its real issuing authority, source URL,
document type, and validity dates so the RAG layer can attribute and filter.

Idempotent: re-running updates nothing that already exists (SHA-256 hash of
content).  Run from the repo root:

    python scripts/seed_knowledge_base.py --dir data/knowledge/seed
"""
import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apps", "api"))

from app.ingestion.knowledge_ingestion import get_knowledge_ingestion_service  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("seed_knowledge")

# filename -> {title, source_url, authority, document_type,
#              publication_date, effective_date, source_reference, tags}
DOCS = {
    "fishing_boats_inspection_rules_1988.pdf": {
        "title": "Merchant Shipping (Indian Fishing Boats Inspection) Rules, 1988",
        "source_url": "https://fisheries.goa.gov.in/wp-content/uploads/2024/01/2.MERCHANT-SHIPPING-INDIAN-FISHING-BOATS-INSPECTION-RULES-1988.pdf",
        "authority": "Ministry of Surface Transport (Shipping Wing)",
        "document_type": "regulation",
        "publication_date": "1988-12-12",
        "effective_date": "1988-12-12",
        "source_reference": "G.S.R. 922(E)",
        "tags": ["fishing boats", "inspection", "certification", "safety"],
    },
    "fishing_boats_registration_rules_1988.pdf": {
        "title": "Merchant Shipping (Registration of Indian Fishing Boats) Rules, 1988",
        "source_url": "https://dgma.gov.in/download/1758280393_68cd3ac985b50_1753939983-688b000f6bb4e-ms-rules-fishingboats1988-260212.pdf",
        "authority": "Ministry of Surface Transport (Shipping Wing)",
        "document_type": "regulation",
        "publication_date": "1988-10-07",
        "effective_date": "1988-10-07",
        "source_reference": "G.S.R. 866(E)",
        "tags": ["fishing boats", "registration", "registry"],
    },
    "merchant_shipping_act_2025.pdf": {
        "title": "The Merchant Shipping Act, 2025",
        "source_url": "https://dgma.gov.in/download/1763973754_69241a7a5c4c1_the-merchant-shipping-act2025.pdf",
        "authority": "Directorate General of Shipping",
        "document_type": "regulation",
        "publication_date": "2025-10-01",
        "effective_date": "2025-10-01",
        "source_reference": "Act 24 of 2025",
        "tags": ["merchant shipping", "vessels", "maritime law"],
    },
    "ms_fishing_vessels_rules_2026.pdf": {
        "title": "Draft Merchant Shipping (Fishing Vessels) Rules, 2026",
        "source_url": "https://shipmin.gov.in/sites/default/files/Draft%20Merchant%20Shipping%20%28Fishing%20Vessels%29%20Rules%2C%202026.pdf",
        "authority": "Ministry of Ports, Shipping & Waterways",
        "document_type": "regulation",
        "publication_date": "2026-01-01",
        "effective_date": None,  # draft - not yet in force
        "source_reference": "G.S.R. ____ (E)",
        "tags": ["fishing vessels", "draft rules", "registration", "safety"],
    },
    "unclos_e.pdf": {
        "title": "United Nations Convention on the Law of the Sea (UNCLOS)",
        "source_url": "https://dgma.gov.in/download/1758280393_68cd3ac9ed07c_1754047157-688ca2b597043-unclos-e.pdf",
        "authority": "United Nations",
        "document_type": "regulation",
        "publication_date": "1982-12-10",
        "effective_date": "1994-11-16",
        "source_reference": "UNCLOS 1982",
        "tags": ["unclos", "territorial sea", "exclusive economic zone", "international law"],
    },
    "mh_mfr_act_1981_prs.pdf": {
        "title": "The Maharashtra Marine Fishing Regulation Act, 1981",
        "source_url": "https://prsindia.org/files/bills_acts/acts_states/maharashtra/1981/1981MH54.pdf",
        "authority": "Government of Maharashtra",
        "document_type": "regulation",
        "publication_date": "1981-09-23",
        "effective_date": "1981-09-23",
        "source_reference": "Maharashtra Act No. LIV of 1981",
        "tags": ["maharashtra", "fishing regulation", "territorial waters"],
    },
    "maharashtra_purse_seine_order_1999.pdf": {
        "title": "Maharashtra order prohibiting purse-seine gear and landing, 1999",
        "source_url": "https://faolex.fao.org/docs/pdf/ind117731.pdf",
        "authority": "Government of Maharashtra, Fisheries Department",
        "document_type": "notice",
        "publication_date": "1999-10-13",
        "effective_date": "1999-10-13",
        "source_reference": "No. Lavesu-499/14141/(C.R.-88)/ADF-14",
        "tags": ["maharashtra", "purse seine", "gear restriction", "territorial waters", "mirkarwada"],
    },
    "maharashtra_mls_gazette_2023.pdf": {
        "title": "Maharashtra Minimum Legal Size (MLS) Notification, 2023",
        "source_url": "http://eprints.cmfri.org.in/17640/1/Maharashtra%20Govt.%20Gazette%20Notification_2023_MLS.pdf",
        "authority": "Government of Maharashtra, Fisheries Department",
        "document_type": "regulation",
        "publication_date": "2023-11-02",
        "effective_date": "2023-11-02",
        "source_reference": "Gazette Part IV(B) Issue 149(2) No. 414",
        "tags": ["maharashtra", "minimum legal size", "juvenile fish", "conservation"],
    },
}


async def run(directory: str, dry_run: bool = False) -> None:
    service = get_knowledge_ingestion_service()
    seed_dir = os.path.abspath(directory)
    results = {"inserted": [], "unchanged": [], "failed": []}

    for filename, meta in DOCS.items():
        path = os.path.join(seed_dir, filename)
        if not os.path.exists(path):
            results["failed"].append((filename, "file not found"))
            log.error("missing: %s", path)
            continue
        with open(path, "rb") as fh:
            content = fh.read()
        log.info("ingesting %s (%d bytes)", filename, len(content))
        if dry_run:
            continue
        result = await service.ingest_document(
            content,
            filename=filename,
            mime_type="application/pdf",
            metadata={
                "title": meta["title"],
                "source_url": meta["source_url"],
                "authority": meta["authority"],
                "document_type": meta["document_type"],
                "publication_date": meta["publication_date"],
                "effective_date": meta["effective_date"],
                "expiry_date": None,
                "source_reference": meta["source_reference"],
                "tags": meta["tags"],
            },
        )
        if result.document_id:
            status = result.status
            row = {
                "title": meta["title"],
                "status": status,
                "document_id": result.document_id,
                "chunks": result.chunks_total,
            }
            if status == "inserted":
                results["inserted"].append(row)
            else:
                results["unchanged"].append(row)
            log.info(
                "%s: status=%s document_id=%s chunks=%s",
                filename, status, result.document_id, result.chunks_total)
        else:
            results["failed"].append((filename, result.error or result.status))
            log.error("%s: failed: %s", filename, result.error or result.status)

    if dry_run:
        print(f"[dry-run] would ingest {len(DOCS)} documents from {seed_dir}")
        return

    print("\n=== SEED SUMMARY ===")
    print(f"inserted: {len(results['inserted'])}")
    for row in results["inserted"]:
        print(f"  + {row['title']} (id={row['document_id']}, chunks={row['chunks']}, {row['status']})")
    print(f"already present / unchanged: {len(results['unchanged'])}")
    for row in results["unchanged"]:
        print(f"  = {row['title']} (id={row['document_id']}, chunks={row['chunks']})")
    if results["failed"]:
        print(f"failed: {len(results['failed'])}")
        for name, why in results["failed"]:
            print(f"  x {name}: {why}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the curated knowledge base with real marine regulations")
    parser.add_argument("--dir", default="data/knowledge/seed", help="directory containing the seed PDFs")
    parser.add_argument("--dry-run", action="store_true", help="validate inputs without writing")
    args = parser.parse_args()
    asyncio.run(run(args.dir, dry_run=args.dry_run))


if __name__ == "__main__":
    main()