"""
SQLAlchemy database models for the application.
Asistente de recopilación y análisis de datos de organizaciones de la sociedad civil
lideradas por mujeres en Colombia
"""
from datetime import datetime
from typing import Optional
import enum
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    ForeignKey, JSON, UniqueConstraint, Enum
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class TerritorialScope(enum.Enum):
    """
    Enum for territorial scope of organizations in Colombia.
    """
    MUNICIPAL = "MUNICIPAL"           # Single municipality
    DEPARTAMENTAL = "DEPARTAMENTAL"   # Single department
    REGIONAL = "REGIONAL"             # Multiple departments (region)
    NACIONAL = "NACIONAL"             # National level
    INTERNACIONAL = "INTERNACIONAL"   # International (counts as nacional for calculations)


class OrganizationApproach(enum.Enum):
    """
    Enum for the approach/origin of an organization.
    """
    BOTTOM_UP = "BOTTOM_UP"           # From the community/pueblo (grassroots)
    TOP_DOWN = "TOP_DOWN"             # From government/state initiative
    MIXED = "MIXED"                   # Mixed approach
    UNKNOWN = "UNKNOWN"               # Unknown


class PendingItemType(enum.Enum):
    """
    Type of pending item awaiting user validation.
    """
    ORGANIZATION = "organization"
    INFO_SOURCE = "info_source"
    ORGANIZATION_UPDATE = "organization_update"


class Organization(Base):
    """
    Model representing a civil society organization led by women for peace-building in Colombia.
    (Organización de la sociedad civil liderada por mujeres constructoras de paz)
    """
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    
    # Geographic coordinates (main location/headquarters)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Colombian territorial scope
    territorial_scope = Column(
        Enum(TerritorialScope), 
        nullable=True, 
        default=TerritorialScope.MUNICIPAL,
        index=True
    )
    # DANE department code (e.g., "11" for Bogotá, "05" for Antioquia)
    department_code = Column(String(10), nullable=True, index=True)
    # DANE municipality code (e.g., "11001" for Bogotá)
    municipality_code = Column(String(10), nullable=True, index=True)
    # For REGIONAL scope: list of department codes
    department_codes = Column(JSON, nullable=True)  # ["05", "08", "13"]
    
    # Organization details
    years_active = Column(Integer, nullable=True)  # Years the organization has been active
    women_count = Column(Integer, nullable=True)  # Number of women members
    leader_is_woman = Column(Boolean, nullable=True)  # Is the leader a woman?
    leader_name = Column(String(255), nullable=True)  # Name of the leader
    approach = Column(
        Enum(OrganizationApproach),
        nullable=True,
        default=OrganizationApproach.UNKNOWN,
        index=True
    )  # Bottom-up (grassroots) or top-down (government initiative)
    
    # Peace-building focus
    is_peace_building = Column(Boolean, default=True, index=True)  # Focus on peace construction
    
    # International flag (for display purposes, counts as nacional in calculations)
    is_international = Column(Boolean, default=False, index=True)
    
    # Verification status
    verified = Column(Boolean, default=False, index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    variables = relationship("Variable", back_populates="organization", cascade="all, delete-orphan")
    locations = relationship("Location", back_populates="organization", cascade="all, delete-orphan")
    links = relationship("OrganizationLink", back_populates="organization", cascade="all, delete-orphan")
    venn_results = relationship("VennResult", back_populates="organization", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Organization(id={self.id}, name='{self.name}')>"


class Variable(Base):
    """
    Model representing a scraped variable/data point.
    Each variable belongs to an organization and stores JSON data.
    """
    __tablename__ = "variables"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Variable identification
    key = Column(String(100), nullable=False, index=True)
    value = Column(JSON, nullable=False)
    
    # Source and verification
    source_url = Column(String(500), nullable=True)
    verified = Column(Boolean, default=False, index=True)
    
    # Timestamps
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationship
    organization = relationship("Organization", back_populates="variables")
    
    # Ensure unique key per organization
    __table_args__ = (
        UniqueConstraint('organization_id', 'key', name='uq_organization_variable_key'),
    )
    
    def __repr__(self):
        return f"<Variable(id={self.id}, key='{self.key}', organization_id={self.organization_id})>"


class Location(Base):
    """
    Model representing a geographic location with GeoJSON data.
    Used for map visualization.
    """
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Location data
    name = Column(String(255), nullable=False)
    geojson = Column(JSON, nullable=False)  # GeoJSON geometry
    properties = Column(JSON, nullable=True)  # Additional properties
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    organization = relationship("Organization", back_populates="locations")
    
    def __repr__(self):
        return f"<Location(id={self.id}, name='{self.name}')>"


class ScrapeLog(Base):
    """
    Model for logging scraping operations.
    """
    __tablename__ = "scrape_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Scrape details
    status = Column(String(50), nullable=False)  # success, error, running
    message = Column(Text, nullable=True)
    variables_found = Column(Integer, default=0)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<ScrapeLog(id={self.id}, status='{self.status}')>"


class OrganizationLink(Base):
    """
    Model representing additional links for an organization.
    Used to define multiple URLs to scrape per organization.
    """
    __tablename__ = "organization_links"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    url = Column(String(500), nullable=False)
    link_type = Column(String(100), nullable=True)  # e.g., "main", "services", "contact"
    description = Column(Text, nullable=True)
    
    # Scraping status
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    scrape_status = Column(String(50), nullable=True)  # success, error, pending
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    organization = relationship("Organization", back_populates="links")
    
    def __repr__(self):
        return f"<OrganizationLink(id={self.id}, url='{self.url}')>"


class VennVariable(Base):
    """
    Model representing a Venn diagram variable definition.
    These are the variables that can be used to create Venn diagrams.
    """
    __tablename__ = "venn_variables"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    data_type = Column(String(50), default="list")  # list, count, boolean
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    proxies = relationship("VennProxy", back_populates="venn_variable", cascade="all, delete-orphan")
    results = relationship("VennResult", back_populates="venn_variable", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<VennVariable(id={self.id}, name='{self.name}')>"


class VennProxy(Base):
    """
    Model representing a proxy (search term/pattern) for a Venn variable.
    Proxies are keywords or patterns used to identify the variable in scraped content.
    
    Territorial validation:
    - applicable_scopes defines which organizational scopes can be activated by this proxy
    - If None/empty, the proxy applies to ALL scopes (no restriction)
    - Example: A proxy for "municipal program X" would have applicable_scopes=["MUNICIPAL"]
    - Example: A generic proxy "peace building" would have applicable_scopes=null (all scopes)
    
    Hierarchy rules:
    - MUNICIPAL: Can only match proxies with MUNICIPAL in applicable_scopes
    - DEPARTAMENTAL: Can match DEPARTAMENTAL and MUNICIPAL (contains municipalities)
    - REGIONAL: Can match REGIONAL, DEPARTAMENTAL, MUNICIPAL
    - NACIONAL: Can match all scopes
    - INTERNACIONAL: Can match all scopes (treated as NACIONAL)
    """
    __tablename__ = "venn_proxies"
    
    id = Column(Integer, primary_key=True, index=True)
    venn_variable_id = Column(Integer, ForeignKey("venn_variables.id"), nullable=False, index=True)
    
    term = Column(String(255), nullable=False)  # Search term or pattern
    is_regex = Column(Boolean, default=False)  # Whether term is a regex pattern
    weight = Column(Float, default=1.0)  # Weight for scoring
    
    # Territorial applicability
    # JSON array of TerritorialScope values, e.g., ["MUNICIPAL", "DEPARTAMENTAL"]
    # If NULL or empty, proxy applies to ALL scopes (universal proxy)
    applicable_scopes = Column(JSON, nullable=True)  # List of TerritorialScope values
    
    # Location specificity (optional, for place-specific proxies)
    # Example: proxy "Programa de Medellín" applies only to Medellín
    location_restriction = Column(JSON, nullable=True)  # {"department_code": "05", "municipality_code": "05001"}
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    venn_variable = relationship("VennVariable", back_populates="proxies")
    
    def __repr__(self):
        return f"<VennProxy(id={self.id}, term='{self.term}', scopes={self.applicable_scopes})>"


class VennResultSource(enum.Enum):
    """
    Source of a Venn result value.
    """
    MANUAL = "manual"           # User manually set the value
    AUTOMATIC = "automatic"     # Calculated from proxy search
    MIXED = "mixed"             # User modified automatic result


class VennResultStatus(enum.Enum):
    """
    Verification status of a Venn result.
    """
    PENDING = "pending"         # Awaiting user verification
    VERIFIED = "verified"       # User verified as correct
    REJECTED = "rejected"       # User rejected the result
    MODIFIED = "modified"       # User modified the value


class VennResult(Base):
    """
    Model representing the result (0 or 1) of a Venn variable for a specific organization.
    This stores whether an organization meets the criteria of a particular Venn variable.
    Results can be:
    - Set manually by the user (1 or 0)
    - Calculated automatically based on proxy search results
    
    Automatic results require user verification before being considered final.
    """
    __tablename__ = "venn_results"
    __table_args__ = (
        UniqueConstraint('organization_id', 'venn_variable_id', name='uq_venn_result_org_var'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    venn_variable_id = Column(Integer, ForeignKey("venn_variables.id"), nullable=False, index=True)
    
    # Result value (0 or 1, stored as boolean)
    value = Column(Boolean, nullable=False, default=False)  # True=1, False=0
    
    # Source of the result
    source = Column(
        Enum(VennResultSource),
        nullable=False,
        default=VennResultSource.MANUAL
    )
    
    # If automatic, stores info about the search that produced this result
    search_score = Column(Float, nullable=True)  # Aggregate score from proxy matches
    matched_proxies = Column(JSON, nullable=True)  # List of proxy IDs/terms that matched
    source_urls = Column(JSON, nullable=True)  # URLs where matches were found
    
    # ========== VERIFICATION FIELDS ==========
    # Verification status
    verification_status = Column(
        Enum(VennResultStatus),
        nullable=False,
        default=VennResultStatus.PENDING,
        index=True
    )
    
    # User verification
    verified_by = Column(String(100), nullable=True)  # User who verified
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_notes = Column(Text, nullable=True)  # User's notes on verification
    
    # Original value (if modified by user)
    original_value = Column(Boolean, nullable=True)  # Store original auto-detected value
    original_score = Column(Float, nullable=True)  # Original confidence score
    
    # Notes for manual entries or user modifications
    notes = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="venn_results")
    venn_variable = relationship("VennVariable", back_populates="results")
    
    def __repr__(self):
        return f"<VennResult(org={self.organization_id}, var={self.venn_variable_id}, value={self.value}, status={self.verification_status})>"


class ScrapingConfig(Base):
    """
    Model for storing scraping configuration.
    """
    __tablename__ = "scraping_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, default="default")
    
    # Playwright settings
    max_depth = Column(Integer, default=2)  # Maximum depth of links to follow
    timeout = Column(Integer, default=30000)  # Page timeout in ms
    wait_time = Column(Integer, default=2000)  # Wait after page load in ms
    
    # Request settings
    max_pages_per_association = Column(Integer, default=10)
    follow_external_links = Column(Boolean, default=False)
    respect_robots_txt = Column(Boolean, default=True)
    
    # Browser settings
    headless = Column(Boolean, default=True)
    user_agent = Column(String(500), nullable=True)
    viewport_width = Column(Integer, default=1280)
    viewport_height = Column(Integer, default=720)
    
    # Rate limiting
    delay_between_requests = Column(Integer, default=1000)  # ms
    max_concurrent_pages = Column(Integer, default=3)
    
    # Active config
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<ScrapingConfig(id={self.id}, name='{self.name}')>"


class ScrapingSession(Base):
    """
    Model for tracking scraping sessions with progress.
    """
    __tablename__ = "scraping_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Session info
    status = Column(String(50), default="pending")  # pending, running, completed, failed, cancelled
    
    # Progress tracking
    total_organizations = Column(Integer, default=0)
    processed_organizations = Column(Integer, default=0)
    total_links = Column(Integer, default=0)
    processed_links = Column(Integer, default=0)
    variables_found = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    
    # Current processing
    current_organization_id = Column(Integer, nullable=True)
    current_url = Column(String(500), nullable=True)
    progress_percent = Column(Float, default=0.0)
    
    # Configuration used
    config_id = Column(Integer, ForeignKey("scraping_configs.id"), nullable=True)
    
    # Results summary
    results_summary = Column(JSON, nullable=True)
    error_log = Column(JSON, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ScrapingSession(id={self.id}, status='{self.status}')>"


class ScrapedData(Base):
    """
    Model for storing individual scraped data items with verification status.
    """
    __tablename__ = "scraped_data"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("scraping_sessions.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Variable info
    variable_key = Column(String(100), nullable=False, index=True)
    variable_value = Column(JSON, nullable=False)
    
    # Source
    source_url = Column(String(500), nullable=False)
    source_context = Column(Text, nullable=True)  # Surrounding text for context
    
    # Data scope - the territorial level this data affects
    data_scope = Column(
        Enum(TerritorialScope),
        nullable=True,
        default=None,
        index=True
    )  # municipal, departamental, regional, nacional, internacional
    
    # Linked Venn variable (if this data relates to a Venn variable)
    venn_variable_id = Column(Integer, ForeignKey("venn_variables.id"), nullable=True, index=True)
    
    # Verification
    auto_verified = Column(Boolean, default=False)  # Result of auto-verification
    auto_verification_score = Column(Float, nullable=True)  # Confidence score
    auto_verification_reason = Column(Text, nullable=True)  # Explanation
    
    manually_verified = Column(Boolean, nullable=True)  # None = not reviewed
    verified_by = Column(String(100), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # When verified, does this confirm the Venn variable?
    confirms_venn_variable = Column(Boolean, nullable=True)  # True=Yes(1), False=No(0), None=Not applicable
    
    # Metadata
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ScrapedData(id={self.id}, key='{self.variable_key}')>"


class InformationSource(Base):
    """
    Model for storing general information sources used by the scraper agent.
    These are global sources, not specific to any organization.
    """
    __tablename__ = "information_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Source identification
    name = Column(String(255), nullable=False, index=True)
    url = Column(String(500), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Source type
    source_type = Column(String(100), nullable=True)  # government, ngo, news, academic, registry, etc.
    
    # Reliability
    reliability_score = Column(Float, default=0.5)  # 0.0 - 1.0
    priority = Column(Integer, default=5)  # 1-10, higher = more priority
    
    # Verification
    verified = Column(Boolean, default=False, index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    suggested_by_agent = Column(Boolean, default=False)  # True if suggested by AI agent
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_successful_scrape = Column(DateTime(timezone=True), nullable=True)
    error_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<InformationSource(id={self.id}, name='{self.name}')>"


class VennOperationType(enum.Enum):
    """
    Logical operation types for Venn intersections.
    """
    INTERSECTION = "intersection"   # A ∩ B (AND) - both must be true
    UNION = "union"                # A ∪ B (OR) - at least one must be true
    DIFFERENCE = "difference"      # A - B - set difference (A true, B false)
    EXCLUSIVE = "exclusive"        # A ⊕ B (XOR) - exactly one is true


class VennIntersection(Base):
    """
    Model representing a logical combination of Venn variables/proxies.
    
    NEW SYSTEM: Uses logic_expression for complex boolean expressions.
    
    Logic Expression Format (JSON tree):
    {
        "type": "AND|OR|proxy|variable|NOT",
        "children": [...],  // For AND/OR operators
        "id": <int>,        // For proxy/variable leaf nodes
        "negate": <bool>    // Optional, to negate the result
    }
    
    Examples:
    - A AND B: {"type": "AND", "children": [{"type": "proxy", "id": 1}, {"type": "proxy", "id": 2}]}
    - (A OR B) AND C: {"type": "AND", "children": [{"type": "OR", "children": [A, B]}, C]}
    - A AND NOT B: {"type": "AND", "children": [{"type": "proxy", "id": 1}, {"type": "proxy", "id": 2, "negate": true}]}
    """
    __tablename__ = "venn_intersections"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Human-readable name for the intersection
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    
    # Display properties (for diagram visualization)
    display_label = Column(String(100), nullable=True)  # Short label for diagram
    color = Column(String(20), nullable=True)  # Hex color for visualization
    
    # ==========================================================================
    # NEW LOGIC EXPRESSION SYSTEM
    # ==========================================================================
    # JSON tree structure for complex boolean expressions with nested AND/OR
    logic_expression = Column(JSON, nullable=True)
    
    # True if using the new expression system (for backward compatibility)
    use_logic_expression = Column(Boolean, default=False)
    
    # Human-readable expression for display (e.g., "(Justicia OR Verdad) AND Seguridad")
    expression_display = Column(Text, nullable=True)
    
    # ==========================================================================
    # LEGACY FIELDS (kept for backward compatibility)
    # ==========================================================================
    # Primary operation type (legacy - use logic_expression instead)
    operation = Column(
        Enum(VennOperationType),
        nullable=False,
        default=VennOperationType.INTERSECTION
    )
    
    # For complex expressions, store the formula as JSON (legacy)
    formula = Column(JSON, nullable=True)
    
    # Simple case: list of variable IDs for direct operations (legacy)
    variable_ids = Column(JSON, nullable=True)
    
    # For difference operations (legacy)
    include_ids = Column(JSON, nullable=True)
    exclude_ids = Column(JSON, nullable=True)
    
    # Proxy-based intersections (legacy)
    include_proxy_ids = Column(JSON, nullable=True)
    exclude_proxy_ids = Column(JSON, nullable=True)
    use_proxies = Column(Boolean, default=False)
    
    # Metadata
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    results = relationship("VennIntersectionResult", back_populates="intersection", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<VennIntersection(id={self.id}, name='{self.name}', logic={self.use_logic_expression})>"


class VennIntersectionResult(Base):
    """
    Computed result of a Venn intersection for a specific organization.
    
    This is DERIVED from VennResult values, not scraped directly.
    Recalculated whenever component VennResults change.
    """
    __tablename__ = "venn_intersection_results"
    __table_args__ = (
        UniqueConstraint('organization_id', 'intersection_id', name='uq_venn_intersection_result'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    intersection_id = Column(Integer, ForeignKey("venn_intersections.id"), nullable=False, index=True)
    
    # Computed result (0 or 1)
    value = Column(Boolean, nullable=False, default=False)
    
    # Component values at time of calculation (for debugging/audit)
    component_values = Column(JSON, nullable=True)  # {"var_name": value, ...}
    
    # Calculation metadata
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    is_stale = Column(Boolean, default=False, index=True)  # True if component results changed
    
    # Optional manual override
    manual_override = Column(Boolean, nullable=True)  # If not null, use this instead of calculated
    override_reason = Column(Text, nullable=True)
    
    # Relationships
    intersection = relationship("VennIntersection", back_populates="results")
    
    def __repr__(self):
        return f"<VennIntersectionResult(org={self.organization_id}, intersection={self.intersection_id}, value={self.value})>"


class SourceType(enum.Enum):
    """
    Type of source where a match was found.
    """
    MAIN_PAGE = "main_page"           # Organization's main website
    SUBPAGE = "subpage"               # Internal subpage
    PDF = "pdf"                       # PDF document
    SOCIAL_MEDIA = "social_media"     # Social media profile
    NEWS = "news"                     # News article
    GOVERNMENT = "government"         # Government portal
    REGISTRY = "registry"             # Official registry
    SEARCH_RESULT = "search_result"   # Web search result (Tavily)
    DESCRIPTION = "description"       # Organization's stored description
    OTHER = "other"


class VennMatchEvidence(Base):
    """
    Model for storing detailed evidence of proxy matches.
    
    When a proxy term is found in scraped content, this records:
    - Exact URL where found
    - Type of source
    - Text fragment showing the context
    - Location within the document (xpath, paragraph, section)
    - Scraping timestamp and session context
    
    Used for audit trail and manual verification.
    """
    __tablename__ = "venn_match_evidence"
    __table_args__ = (
        # Index for fast lookups by result
        {'comment': 'Stores evidence/proof of proxy matches for verification'}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Link to the VennResult this evidence supports
    venn_result_id = Column(Integer, ForeignKey("venn_results.id"), nullable=False, index=True)
    
    # Which proxy was matched
    venn_proxy_id = Column(Integer, ForeignKey("venn_proxies.id"), nullable=False, index=True)
    
    # Source information
    source_url = Column(String(1000), nullable=False)  # Exact URL where match was found
    source_type = Column(
        Enum(SourceType),
        nullable=False,
        default=SourceType.MAIN_PAGE
    )
    
    # Location within the document
    text_fragment = Column(Text, nullable=True)  # Surrounding text (context)
    matched_text = Column(String(500), nullable=True)  # Exact matched portion
    xpath = Column(String(500), nullable=True)  # XPath to element if available
    css_selector = Column(String(500), nullable=True)  # CSS selector if available
    paragraph_number = Column(Integer, nullable=True)  # Paragraph index in document
    section_title = Column(String(255), nullable=True)  # Section heading if identifiable
    
    # Match quality
    match_score = Column(Float, default=1.0)  # Confidence score for this specific match
    is_exact_match = Column(Boolean, default=True)  # Exact term match vs fuzzy/semantic
    
    # Scraping context
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    scraping_session_id = Column(Integer, ForeignKey("scraping_sessions.id"), nullable=True)
    page_title = Column(String(500), nullable=True)  # Title of the page where found
    page_language = Column(String(10), nullable=True)  # Detected language
    
    # Validation
    is_valid = Column(Boolean, nullable=True)  # User validation: True=valid, False=false positive, None=pending
    validated_by = Column(String(100), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validation_notes = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    venn_result = relationship("VennResult", backref="match_evidences")
    
    def __repr__(self):
        return f"<VennMatchEvidence(id={self.id}, url='{self.source_url[:50]}...', proxy_id={self.venn_proxy_id})>"


class PendingValidation(Base):
    """
    Model for items pending user validation from the chat.
    Used for both new organizations and new information sources.
    """
    __tablename__ = "pending_validations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Type and reference
    item_type = Column(
        Enum(PendingItemType),
        nullable=False,
        index=True
    )  # organization, info_source, organization_update
    
    # Session tracking
    session_id = Column(String(100), nullable=False, index=True)
    
    # The data to be validated (JSON)
    pending_data = Column(JSON, nullable=False)
    
    # Agent reasoning
    agent_reasoning = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    source_urls = Column(JSON, nullable=True)  # List of URLs where data was found
    
    # Status
    status = Column(String(50), default="pending")  # pending, approved, rejected, expired
    
    # User decision
    user_decision = Column(String(50), nullable=True)  # approved, rejected, modified
    user_modifications = Column(JSON, nullable=True)  # Modifications made by user
    decision_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Auto-expire pending items
    
    def __repr__(self):
        return f"<PendingValidation(id={self.id}, type='{self.item_type}', status='{self.status}')>"
