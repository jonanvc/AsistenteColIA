"""
Scraping execution script
Run scraping for one or all organizations
"""
import asyncio
import sys
import json

sys.path.insert(0, '/app')

from app.services.scraper import scrape_organization, scrape_all_organizations


async def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python run_scrape.py <organization_id>  - Scrape one organization")
        print("  python run_scrape.py --all              - Scrape all organizations")
        return
    
    if sys.argv[1] == "--all":
        print("🕷️  Starting scraping for ALL organizations...")
        results = await scrape_all_organizations()
        print(json.dumps(results, indent=2, default=str))
    else:
        try:
            organization_id = int(sys.argv[1])
            print(f"🕷️  Starting scraping for organization {organization_id}...")
            result = await scrape_organization(organization_id)
            print(json.dumps(result, indent=2, default=str))
        except ValueError:
            print(f"Error: '{sys.argv[1]}' is not a valid organization ID")


if __name__ == "__main__":
    asyncio.run(main())
