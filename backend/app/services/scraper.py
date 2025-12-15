"""
Scraper service using Playwright for headless browser automation.
Scrapes organization websites and extracts relevant data.
"""
import asyncio
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright, Page, Browser
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.base import async_session_maker
from app.models.db_models import Organization, Variable, ScrapeLog


async def save_variable(
    organization_id: int,
    key: str,
    value: Any,
    source_url: str
) -> None:
    """
    Save a scraped variable to the database.
    Uses upsert to update existing variables.
    
    Args:
        organization_id: ID of the organization
        key: Variable key/name
        value: Variable value (will be stored as JSON)
        source_url: URL where the data was scraped from
    """
    async with async_session_maker() as session:
        # Prepare the variable data
        variable_data = {
            "organization_id": organization_id,
            "key": key,
            "value": value if isinstance(value, dict) else {"data": value},
            "source_url": source_url,
            "verified": False,
            "scraped_at": datetime.utcnow()
        }
        
        # Use PostgreSQL upsert (insert or update on conflict)
        stmt = insert(Variable).values(**variable_data)
        stmt = stmt.on_conflict_do_update(
            constraint='uq_organization_variable_key',
            set_={
                "value": variable_data["value"],
                "source_url": variable_data["source_url"],
                "scraped_at": variable_data["scraped_at"]
            }
        )
        
        await session.execute(stmt)
        await session.commit()


async def extract_services(page: Page) -> List[str]:
    """
    Extract services from a page.
    Looks for common patterns like lists, cards, etc.
    """
    services = []
    
    # Try different selectors for service lists
    selectors = [
        "ul.services li",
        ".service-item",
        "[class*='service'] h3",
        "[class*='service'] .title",
        "section.services li",
        ".card.service h3"
    ]
    
    for selector in selectors:
        try:
            elements = await page.query_selector_all(selector)
            for el in elements:
                text = await el.inner_text()
                if text and len(text) < 200:
                    services.append(text.strip())
        except Exception:
            continue
    
    # If no structured data found, try to extract from page content
    if not services:
        try:
            content = await page.content()
            # Look for service-related keywords
            patterns = [
                r'(?:servicios?|services?):\s*([^<]+)',
                r'(?:ofrecemos|we offer):\s*([^<]+)'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                services.extend(matches)
        except Exception:
            pass
    
    return list(set(services))[:20]  # Limit and deduplicate


async def extract_contact_info(page: Page) -> Dict[str, Any]:
    """
    Extract contact information from a page.
    """
    contact = {}
    
    try:
        # Email
        content = await page.content()
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)
        if emails:
            contact["email"] = list(set(emails))[:3]
        
        # Phone
        phones = re.findall(r'(?:\+\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}', content)
        if phones:
            contact["phone"] = list(set(phones))[:3]
        
        # Address - try to find structured data
        address_selectors = ["address", ".address", "[class*='contact'] p", "[class*='direccion']"]
        for selector in address_selectors:
            try:
                el = await page.query_selector(selector)
                if el:
                    contact["address"] = await el.inner_text()
                    break
            except Exception:
                continue
    except Exception:
        pass
    
    return contact


async def extract_social_links(page: Page) -> Dict[str, str]:
    """
    Extract social media links from a page.
    """
    social = {}
    
    platforms = {
        "facebook": r'facebook\.com/[\w\.-]+',
        "twitter": r'twitter\.com/[\w\.-]+',
        "instagram": r'instagram\.com/[\w\.-]+',
        "linkedin": r'linkedin\.com/(?:company|in)/[\w\.-]+',
        "youtube": r'youtube\.com/(?:channel|user)/[\w\.-]+'
    }
    
    try:
        content = await page.content()
        for platform, pattern in platforms.items():
            match = re.search(pattern, content)
            if match:
                social[platform] = f"https://{match.group(0)}"
    except Exception:
        pass
    
    return social


async def scrape_page(page: Page, url: str, organization_id: int) -> Dict[str, Any]:
    """
    Scrape a single page and extract all relevant data.
    
    Args:
        page: Playwright page instance
        url: URL to scrape
        organization_id: Organization ID for saving variables
        
    Returns:
        Dictionary with all extracted data
    """
    data = {
        "url": url,
        "scraped_at": datetime.utcnow().isoformat()
    }
    
    try:
        # Navigate to page with timeout
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)  # Wait for JS to load
        
        # Extract page title
        title = await page.title()
        if title:
            data["title"] = title
            await save_variable(organization_id, "page_title", title, url)
        
        # Extract meta description
        try:
            meta = await page.query_selector('meta[name="description"]')
            if meta:
                description = await meta.get_attribute("content")
                if description:
                    data["meta_description"] = description
                    await save_variable(organization_id, "meta_description", description, url)
        except Exception:
            pass
        
        # Extract services
        services = await extract_services(page)
        if services:
            data["services"] = services
            await save_variable(organization_id, "servicios", services, url)
        
        # Extract contact info
        contact = await extract_contact_info(page)
        if contact:
            data["contact"] = contact
            await save_variable(organization_id, "contacto", contact, url)
        
        # Extract social links
        social = await extract_social_links(page)
        if social:
            data["social_media"] = social
            await save_variable(organization_id, "redes_sociales", social, url)
        
        # Extract main content text (for NLP processing)
        try:
            main_selectors = ["main", "article", ".content", "#content", ".main-content"]
            for selector in main_selectors:
                el = await page.query_selector(selector)
                if el:
                    text = await el.inner_text()
                    if text and len(text) > 100:
                        # Limit text size
                        data["main_content"] = text[:5000]
                        await save_variable(
                            organization_id,
                            "contenido_principal",
                            {"text": text[:5000], "char_count": len(text)},
                            url
                        )
                        break
        except Exception:
            pass
        
    except Exception as e:
        data["error"] = str(e)
    
    return data


async def scrape_organization(organization_id: int) -> Dict[str, Any]:
    """
    Scrape all data for a specific organization.
    
    Args:
        organization_id: ID of the organization to scrape
        
    Returns:
        Dictionary with scraping results
    """
    result = {
        "organization_id": organization_id,
        "status": "started",
        "started_at": datetime.utcnow().isoformat(),
        "variables_found": 0
    }
    
    async with async_session_maker() as session:
        # Get organization
        stmt = select(Organization).where(Organization.id == organization_id)
        db_result = await session.execute(stmt)
        organization = db_result.scalar_one_or_none()
        
        if not organization:
            result["status"] = "error"
            result["message"] = f"Organization {organization_id} not found"
            return result
        
        if not organization.url:
            result["status"] = "error"
            result["message"] = f"Organization {organization.name} has no URL"
            return result
        
        # Log scrape start
        log = ScrapeLog(
            organization_id=organization_id,
            status="running"
        )
        session.add(log)
        await session.commit()
        log_id = log.id
    
    # Start browser and scrape
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        
        try:
            # Create context with common settings
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            # Scrape main page
            main_data = await scrape_page(page, organization.url, organization_id)
            result["main_page"] = main_data
            
            # Try to find and scrape subpages
            subpages_to_try = [
                "/servicios", "/services",
                "/contacto", "/contact",
                "/about", "/nosotros",
                "/programas", "/programs"
            ]
            
            base_url = organization.url.rstrip('/')
            result["subpages"] = []
            
            for subpage in subpages_to_try:
                try:
                    subpage_url = base_url + subpage
                    response = await page.goto(subpage_url, timeout=10000)
                    if response and response.status == 200:
                        subpage_data = await scrape_page(page, subpage_url, organization_id)
                        result["subpages"].append(subpage_data)
                except Exception:
                    continue  # Skip failed subpages
            
            await context.close()
            result["status"] = "success"
            
        except Exception as e:
            result["status"] = "error"
            result["message"] = str(e)
        
        finally:
            await browser.close()
    
    # Count variables and update log
    async with async_session_maker() as session:
        var_count = await session.execute(
            select(Variable).where(Variable.organization_id == organization_id)
        )
        variables = var_count.scalars().all()
        result["variables_found"] = len(variables)
        
        # Update log
        log_stmt = select(ScrapeLog).where(ScrapeLog.id == log_id)
        log_result = await session.execute(log_stmt)
        log = log_result.scalar_one()
        log.status = result["status"]
        log.message = result.get("message")
        log.variables_found = len(variables)
        log.completed_at = datetime.utcnow()
        await session.commit()
    
    result["completed_at"] = datetime.utcnow().isoformat()
    return result


async def scrape_all_organizations() -> List[Dict[str, Any]]:
    """
    Scrape all organizations in the database.
    
    Returns:
        List of scraping results for each organization
    """
    results = []
    
    async with async_session_maker() as session:
        stmt = select(Organization).where(Organization.url.isnot(None))
        db_result = await session.execute(stmt)
        organizations = db_result.scalars().all()
    
    for organization in organizations:
        result = await scrape_organization(organization.id)
        results.append(result)
        # Small delay between scrapes to be respectful
        await asyncio.sleep(2)
    
    return results


# CLI entry point for running scraper directly
if __name__ == "__main__":
    import sys
    
    async def main():
        if len(sys.argv) > 1:
            if sys.argv[1] == "--all":
                results = await scrape_all_organizations()
                print(json.dumps(results, indent=2, default=str))
            else:
                organization_id = int(sys.argv[1])
                result = await scrape_organization(organization_id)
                print(json.dumps(result, indent=2, default=str))
        else:
            print("Usage: python scraper.py <organization_id> | --all")
    
    asyncio.run(main())
