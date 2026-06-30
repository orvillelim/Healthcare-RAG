import os
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

EMBEDDING_MODEL = "nomic-embed-text"
COLLECTION_NAME = "hmo_docs"
# CHROMA_DB_PATH = os.path.join(BASE_DIR, "preprocess1")
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")
LLM_MODEL = "gemini-3.5-flash"


PROVIDERS_NAMES = [
    "cocolife",
    "intellicare",
    "maxicare",
    "medicard",
    "pacificcross",
]


PROVIDERS = {
    "maxicare": {
        "name": "Maxicare Healthcare Corporation",
        "base_url": "https://www.maxicare.com.ph",
        "seed_urls": [
            "https://www.maxicare.com.ph/maxicare-plans/",
            "https://www.maxicare.com.ph/maxicare-plans/mymaxicare/",
            "https://www.maxicare.com.ph/maxicare-plans/prima/",
            "https://www.maxicare.com.ph/maxicare-plans/easyreach/",
            "https://www.maxicare.com.ph/member-section/benefits-and-coverage/",
        ],
        "known_pdfs": [
            "https://irp.cdn-website.com/8fb9e882/files/uploaded/MYMAXICARE%20BROCHURE%202022.pdf",
        ],
        "output_dir": os.path.join(DATA_DIR, "maxicare"),
    },
    "medicard": {
        "name": "MediCard Philippines, Inc.",
        "base_url": "https://www.medicardphils.com",
        "seed_urls": [
            "https://www.medicardphils.com/healthcare-programs/my-medicard/",
            "https://www.medicardphils.com/healthcare-programs/kabayan/",
            "https://www.medicardphils.com/healthcare-programs/vip/",
            "https://www.medicardphils.com/healthcare-programs/medicard-select/",
            "https://www.medicardphils.com/healthcare-programs/rxer/",
            "https://www.medicardphils.com/healthcare-programs/health-plus/",
        ],
        "output_dir": os.path.join(DATA_DIR, "medicard"),
    },
    "intellicare": {
        "name": "Intellicare",
        "base_url": "https://site.intellicare.com.ph",
        "seed_urls": [
            "https://site.intellicare.com.ph/index.php/steps-and-forms/",
            "https://site.intellicare.com.ph/index.php/steps-and-forms-outpatient/",
            "https://site.intellicare.com.ph/index.php/steps-and-forms-in-patient/",
            "https://site.intellicare.com.ph/index.php/steps-and-forms-emergency/",
        ],
        "known_pdfs": [
            "https://site.intellicare.com.ph/wp-content/uploads/2022/06/Access-Guidebook-2022.pdf",
            "https://site.intellicare.com.ph/wp-content/uploads/2019/04/Standard-Guidebook_Benefits_April-2019.pdf",
            "https://site.intellicare.com.ph/wp-content/uploads/2018/08/Standard-Guidebook_Access_July.pdf",
            "https://site.intellicare.com.ph/wp-content/uploads/2018/08/Standard-Guidebook_Benefits_July.pdf",
        ],
        "output_dir": os.path.join(DATA_DIR, "intellicare"),
    },
    "pacific_cross": {
        "name": "Pacific Cross Health Care, Inc.",
        "base_url": "https://www.pacificcross.com.ph",
        "seed_urls": [
            "https://www.pacificcross.com.ph/claim/",
        ],
        "output_dir": os.path.join(DATA_DIR, "pacific_cross"),
    },
    "cocolife": {
        "name": "Cocolife Healthcare",
        "base_url": "https://www.cocolife.com",
        "seed_urls": [
            "https://www.cocolife.com/health-care/",
        ],
        "known_pdfs": [
            "https://www.cocolife.com/wp-content/uploads/2021/11/Benefits-Guidebook-DOWNLOADABLE.pdf",
        ],
        "output_dir": os.path.join(DATA_DIR, "cocolife"),
    },
    "philcare": {
        "name": "PhilCare",
        "base_url": "https://www.philcare.com.ph",
        "seed_urls": [
            "https://www.philcare.com.ph/products/",
            "https://shop.philcare.com.ph/",
        ],
        "output_dir": os.path.join(DATA_DIR, "philcare"),
    },
    "insurance_gov": {
        "name": "Insurance Commission (Philippines)",
        "base_url": "https://www.insurance.gov.ph",
        "seed_urls": [
            "https://www.insurance.gov.ph/hmo/",
            "https://www.insurance.gov.ph/publications/",
        ],
        "known_pdfs": [
            "https://www.insurance.gov.ph/wp-content/uploads/2025/02/"
            "List-of-HMOs-with-CA-Issued-by-the-Insurance-Commission-as-of-31-January-2025.pdf",
        ],
        "output_dir": os.path.join(DATA_DIR, "insurance_gov"),
    },
}


def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
