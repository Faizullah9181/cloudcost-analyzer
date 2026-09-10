"""
Procedural Memory Layer - Skills & Workflows
============================================
PROCEDURAL MEMORY stores "how-to" knowledge - workflows, best practices,
and tool capabilities. Skills are loaded on-demand, not all at startup.

Skills categories:
- Cloud-specific (AWS EC2, Azure VMs, GCP Compute, etc.)
- Cross-cloud (multi-provider comparison, optimization)
- Analysis techniques (forecasting, trend analysis, cost reduction)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SkillCategory(str, Enum):
    """Skill categories"""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    DIGITALOCEAN = "digitalocean"
    CROSS_CLOUD = "cross_cloud"
    ANALYSIS = "analysis"
    OPTIMIZATION = "optimization"


@dataclass
class Skill:
    """
    A procedural memory skill - how-to knowledge.

    Skills are:
    - Modular (one skill = one capability)
    - Markdown-based (easy to update)
    - Category-tagged (searchable)
    - Tag-based (searchable by keywords)
    """

    id: str  # "aws/ec2_cost_analysis"
    name: str  # "EC2 Cost Analysis"
    category: SkillCategory
    content: str  # Markdown content
    tags: list[str] = field(default_factory=list)  # ["cost", "ec2", "trend"]
    providers: list[str] = field(default_factory=list)  # ["aws"]
    token_count: int = 0
    version: str = "1.0"
    updated_at: str = ""
    description: str = ""

    def get_preview(self, max_chars: int = 150) -> str:
        """Get first N chars of skill content"""
        lines = self.content.split("\n")
        preview = " ".join(lines[:3])
        if len(preview) > max_chars:
            preview = preview[:max_chars] + "..."
        return preview

    def matches_query(self, query: str) -> float:
        """
        Score how well this skill matches a query.

        Args:
            query: User query

        Returns:
            Match score (0.0 to 1.0)
        """
        query_lower = query.lower()
        score = 0.0

        # Tag matching (whole words, tolerate plurals: cost/costs, tag/tags)
        tag_hits = sum(
            1 for tag in self.tags if re.search(rf"\b{re.escape(tag.lower())}(s|es)?\b", query_lower)
        )
        if tag_hits:
            score += 0.4 + min(0.2, 0.1 * (tag_hits - 1))

        # Provider matching
        if any(re.search(rf"\b{re.escape(p)}\b", query_lower) for p in self.providers):
            score += 0.2

        # Name / id matching
        if self.name.lower() in query_lower or self.id in query_lower:
            score += 0.3

        # Content matching (phrase appears in the skill body)
        if len(query_lower) > 3 and query_lower in self.content.lower():
            score += 0.2

        return min(score, 1.0)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "tags": self.tags,
            "providers": self.providers,
            "description": self.description,
            "preview": self.get_preview(),
        }


class ProceduralMemory:
    """
    PROCEDURAL MEMORY - Skills library management.

    Skills are:
    - Loaded on-demand (not at startup)
    - Categorized and tagged
    - Reusable across users
    - Versionable
    - Easy to update without code changes
    """

    def __init__(self):
        """Initialize procedural memory"""
        self.skills: dict[str, Skill] = {}
        self.loaded_skills: set[str] = set()  # Track which are in memory
        self._load_builtin_skills()

    # ========== SKILL REGISTRY ==========

    def register_skill(
        self,
        skill_id: str,
        name: str,
        category: SkillCategory,
        content: str,
        tags: list[str | None] = None,
        providers: list[str | None] = None,
        description: str = "",
    ) -> Skill:
        """
        Register a new skill.

        Args:
            skill_id: Unique skill ID (e.g., "aws/ec2_analysis")
            name: Human-readable name
            category: Skill category
            content: Markdown content
            tags: Search tags
            providers: Applicable providers
            description: Brief description

        Returns:
            Registered skill
        """
        skill = Skill(
            id=skill_id,
            name=name,
            category=category,
            content=content,
            tags=tags or [],
            providers=providers or [],
            token_count=len(content.split()),
            description=description,
        )
        self.skills[skill_id] = skill
        return skill

    def _load_builtin_skills(self) -> None:
        """Load built-in skills (without external files)"""

        # AWS Skills
        self.register_skill(
            "aws/ec2_analysis",
            "EC2 Cost Analysis",
            SkillCategory.AWS,
            """# EC2 Cost Analysis Guide

## EC2 Pricing Components
1. **Compute hours** - Instance type and size
2. **Storage (EBS)** - Per GB-month
3. **Data transfer** - Egress charges
4. **Elastic IPs** - When not attached

## Cost Optimization Strategies
- Use Reserved Instances (30-40% savings)
- Spot Instances for non-critical workloads
- Right-size instances based on utilization
- Consider Graviton processors (20% cheaper)

## Analysis Tips
- Compare On-Demand vs Reserved vs Spot pricing
- Check for idle instances
- Monitor EBS volume costs
- Analyze data transfer patterns
""",
            tags=["cost", "ec2", "analysis", "optimization"],
            providers=["aws"],
            description="Analyze EC2 costs and optimization strategies",
        )

        self.register_skill(
            "aws/rds_optimization",
            "RDS Cost Optimization",
            SkillCategory.AWS,
            """# RDS Cost Optimization

## RDS Cost Components
1. **Database instance** - Per hour (varies by type)
2. **Storage** - Per GB-month
3. **Backups** - Storage cost
4. **Data transfer** - Egress charges

## Optimization Techniques
- Use Reserved Instances for predictable workloads
- Enable automated backups with appropriate retention
- Use Aurora for better price/performance
- Consider read replicas for scaling
- Enable Performance Insights for optimization

## Monitoring
- Track database CPU and memory utilization
- Monitor query performance
- Set up CloudWatch alarms
- Regular performance reviews
""",
            tags=["cost", "rds", "database", "optimization"],
            providers=["aws"],
            description="Optimize RDS database costs",
        )

        self.register_skill(
            "aws/s3_management",
            "S3 Storage Cost Reduction",
            SkillCategory.AWS,
            """# S3 Cost Management

## S3 Cost Drivers
1. **Storage class** - Standard, IA, Glacier, etc.
2. **Data volume** - Per GB-month
3. **Request costs** - GET, PUT, DELETE operations
4. **Data transfer** - Egress charges

## Cost Reduction Strategies
- Use S3 Lifecycle policies to transition data
- Move infrequent data to S3-IA or Glacier
- Enable S3 Intelligent-Tiering
- Delete unnecessary versions (versioning)
- Compress objects before storage

## Monitoring
- Enable S3 Storage Lens
- Set up CloudWatch metrics
- Use Cost Explorer for breakdown
- Regular audits of bucket contents
""",
            tags=["cost", "s3", "storage", "optimization"],
            providers=["aws"],
            description="Reduce S3 storage costs",
        )

        # Azure Skills
        self.register_skill(
            "azure/vm_cost_analysis",
            "Azure VM Cost Analysis",
            SkillCategory.AZURE,
            """# Azure Virtual Machine Costs

## VM Cost Components
1. **Compute** - Per hour by VM size and type
2. **OS license** - Windows adds cost
3. **Storage** - Managed disks
4. **Network** - Data transfer, public IPs

## Cost Optimization
- Use Reserved Instances (30-35% discount)
- Spot VMs for dev/test (up to 90% savings)
- Right-size based on actual usage
- Use Azure Hybrid Benefit for Windows/SQL
- Consider Scale Sets for auto-scaling

## Monitoring
- Review Azure Monitor metrics
- Use Cost Management for analysis
- Set up budget alerts
- Regular size optimization reviews
""",
            tags=["cost", "vm", "compute", "azure"],
            providers=["azure"],
            description="Analyze Azure VM costs",
        )

        self.register_skill(
            "azure/storage_analysis",
            "Azure Storage Optimization",
            SkillCategory.AZURE,
            """# Azure Storage Cost Management

## Storage Cost Tiers
1. **Hot** - Frequently accessed
2. **Cool** - Infrequent access (30 days minimum)
3. **Archive** - Rare access (90 days minimum)
4. **Geo-redundancy** - Adds cost

## Optimization Strategies
- Transition old data to Archive
- Use Lifecycle Management policies
- Choose appropriate redundancy level
- Monitor access patterns
- Delete unused storage accounts

## Best Practices
- Review unused storage regularly
- Use automation for tier transitions
- Monitor data retention policies
- Consider regional distribution
""",
            tags=["cost", "storage", "azure", "optimization"],
            providers=["azure"],
            description="Optimize Azure storage costs",
        )

        # GCP Skills
        self.register_skill(
            "gcp/compute_analysis",
            "GCP Compute Engine Analysis",
            SkillCategory.GCP,
            """# GCP Compute Engine Costs

## Compute Pricing Factors
1. **Machine type** - CPU and memory
2. **Commitment discounts** - 1 or 3 years
3. **Preemptible VMs** - Up to 70% cheaper
4. **Custom machines** - Pay for exact resources

## Cost Optimization
- Use Commitment discounts (25-30% savings)
- Use Preemptible VMs for batch jobs
- Right-size machines based on metrics
- Use custom machine types for efficiency
- Enable autoscaling

## Analysis Tips
- Monitor CPU and memory utilization
- Check for idle instances
- Analyze instance scheduling
- Review commitment coverage
""",
            tags=["cost", "compute", "gcp", "analysis"],
            providers=["gcp"],
            description="Analyze GCP Compute Engine costs",
        )

        # DigitalOcean Skills
        self.register_skill(
            "digitalocean/droplet_costs",
            "DigitalOcean Cost Management",
            SkillCategory.DIGITALOCEAN,
            """# DigitalOcean Cost Management

## Billing Model
1. **Droplets** - Hourly, capped at the monthly price of the size
2. **Volumes** - Per GB-month block storage
3. **Load balancers** - Flat monthly price per size unit
4. **Managed databases** - Per node, by plan size
5. **Bandwidth** - Pooled transfer allowance per droplet; overage billed per GB

## Cost Optimization
- Power off is not enough: destroy droplets you are not using (powered-off droplets still bill)
- Snapshot then destroy idle droplets; restore later if needed
- Resize droplets to match utilisation; use CPU-optimised only where needed
- Remove detached volumes and old snapshots
- Consolidate small managed databases

## Analysis Tips
- Use the billing summary for month-to-date usage and invoices for history
- Use resource costs to estimate the run-rate from what is currently deployed
- Compare invoice trend month over month to spot growth
""",
            tags=["cost", "droplet", "digitalocean", "optimization"],
            providers=["digitalocean"],
            description="Understand and reduce DigitalOcean spend",
        )

        # Cross-cloud Skills
        self.register_skill(
            "cross_cloud/multi_cloud_comparison",
            "Multi-Cloud Cost Comparison",
            SkillCategory.CROSS_CLOUD,
            """# Multi-Cloud Cost Analysis

## Comparison Framework
1. **Service equivalence** - Map similar services
2. **Pricing differences** - Compare per-unit costs
3. **Commitment discounts** - Consider RI/Commitment savings
4. **Data transfer** - Cross-cloud egress costs
5. **Support costs** - Enterprise vs standard

## Common Comparisons
- AWS EC2 vs Azure VMs vs GCP Compute Engine
- AWS S3 vs Azure Blob vs GCP Storage
- AWS RDS vs Azure Database vs GCP Cloud SQL

## When to Multi-Cloud
- Avoid vendor lock-in
- Leverage service strengths
- Disaster recovery
- Cost optimization
- Regulatory requirements

## Challenges
- Operational complexity
- Tool and skill requirements
- Data consistency
- Cross-cloud networking
""",
            tags=["comparison", "compare", "cost", "multi-cloud"],
            providers=["aws", "azure", "gcp", "digitalocean"],
            description="Compare costs across cloud providers",
        )

        # Analysis Skills
        self.register_skill(
            "analysis/cost_forecasting",
            "Cost Forecasting Techniques",
            SkillCategory.ANALYSIS,
            """# Cloud Cost Forecasting

## Forecasting Methods
1. **Trend-based** - Extrapolate historical trends
2. **Linear regression** - Model cost growth
3. **Seasonal adjustment** - Account for peaks
4. **Growth-based** - Factor in resource growth

## Factors to Consider
- Historical growth rate
- Seasonal patterns
- Planned changes
- Business growth
- Tech optimization

## Accuracy Improvement
- Use minimum 3 months history
- Account for anomalies
- Adjust for known changes
- Regular reforecasting
- Compare actual vs forecast

## Common Pitfalls
- Ignoring seasonal patterns
- Assuming linear growth
- Not accounting for anomalies
- Insufficient historical data
""",
            tags=["forecast", "analysis", "prediction", "projection"],
            providers=["aws", "azure", "gcp", "digitalocean"],
            description="Techniques for forecasting cloud costs",
        )

        self.register_skill(
            "analysis/cost_reduction_strategies",
            "Cost Reduction Strategies",
            SkillCategory.OPTIMIZATION,
            """# Cloud Cost Reduction Playbook

## Quick Wins (implement immediately)
1. Delete unused resources
2. Stop non-production instances
3. Optimize storage tiers
4. Remove unused volumes
5. Consolidate small instances

## Medium-term (1-3 months)
- Implement Reserved Instances
- Enable autoscaling
- Optimize database configurations
- Review and optimize data transfer
- Consolidate redundant services

## Long-term Strategy
- Architectural optimization
- Consider managed services
- Implement cost allocation tags
- FinOps culture
- Automation and monitoring

## Cost Reduction Targets
- 10-15% quick wins
- 20-30% with RIs
- 30-50% with architectural changes

## Implementation Steps
1. Assess current spending
2. Identify opportunities
3. Prioritize by impact
4. Implement changes
5. Measure results
""",
            tags=["optimization", "optimize", "cost-reduction", "savings", "reduce", "strategy"],
            providers=["aws", "azure", "gcp", "digitalocean"],
            description="Cost reduction strategies and tactics",
        )

    # ========== SKILL LOOKUP ==========

    def get_skill(self, skill_id: str) -> Skill | None:
        """Get a skill by ID"""
        return self.skills.get(skill_id)

    def load_skill(self, skill_id: str) -> Skill | None:
        """
        Load a skill into memory (for injection).

        Args:
            skill_id: Skill ID to load

        Returns:
            Loaded skill or None
        """
        skill = self.skills.get(skill_id)
        if skill:
            self.loaded_skills.add(skill_id)
        return skill

    def unload_skill(self, skill_id: str) -> None:
        """Remove skill from memory (save tokens)"""
        self.loaded_skills.discard(skill_id)

    def get_loaded_skills(self) -> list[Skill]:
        """Get all currently loaded skills"""
        return [self.skills[sid] for sid in self.loaded_skills if sid in self.skills]

    def clear_loaded_skills(self) -> None:
        """Clear all loaded skills"""
        self.loaded_skills.clear()

    # ========== SKILL SEARCH ==========

    def search_skills(
        self,
        query: str,
        category_filter: SkillCategory | None = None,
        provider_filter: str | None = None,
        limit: int = 5,
    ) -> list[Skill]:
        """
        Search for relevant skills.

        Args:
            query: Search query
            category_filter: Filter by category
            provider_filter: Filter by provider
            limit: Max results

        Returns:
            Matching skills ranked by relevance
        """
        results = []

        for skill in self.skills.values():
            # Apply filters
            if category_filter and skill.category != category_filter:
                continue
            if provider_filter and provider_filter not in skill.providers:
                continue

            # Calculate relevance
            score = skill.matches_query(query)
            if score > 0:
                results.append((skill, score))

        # Sort by relevance
        results.sort(key=lambda x: x[1], reverse=True)
        return [skill for skill, _ in results[:limit]]

    def search_by_provider(self, provider: str) -> list[Skill]:
        """Get all skills for a provider"""
        return [s for s in self.skills.values() if provider in s.providers]

    def search_by_category(self, category: SkillCategory) -> list[Skill]:
        """Get all skills in a category"""
        return [s for s in self.skills.values() if s.category == category]

    def search_by_tag(self, tag: str) -> list[Skill]:
        """Get all skills with a tag"""
        return [s for s in self.skills.values() if tag in s.tags]

    # ========== SKILL ASSEMBLY ==========

    def get_relevant_skills(self, query: str, limit: int = 3) -> list[Skill]:
        """
        Identify and load relevant skills for a query.

        Args:
            query: User query
            limit: Max skills to load

        Returns:
            Relevant skills
        """
        # Clear previous skills to save memory
        self.clear_loaded_skills()

        # Find relevant skills
        skills = self.search_skills(query, limit=limit)

        # Load them
        for skill in skills:
            self.load_skill(skill.id)

        return skills

    def assemble_skills_injection(self, max_tokens: int = 2000) -> str:
        """
        Assemble loaded skills for prompt injection.

        Args:
            max_tokens: Max tokens to include

        Returns:
            Formatted skills injection
        """
        loaded = self.get_loaded_skills()
        if not loaded:
            return ""

        lines = ["### Available Skills & Procedures:"]
        lines.append("")

        for skill in loaded:
            lines.append(f"## {skill.name}")
            lines.append(
                f"*Category: {skill.category.value} | Tags: {', '.join(skill.tags)}*"
            )
            lines.append("")
            lines.append(skill.content)
            lines.append("")

        result = "\n".join(lines)

        # Truncate if too long (rough 4 chars per token)
        if len(result.split()) > max_tokens:
            result = result[: max_tokens * 4].rstrip() + "\n...(truncated)"

        return result

    # ========== STATISTICS ==========

    def get_stats(self) -> dict[str, Any]:
        """Get procedural memory statistics"""
        return {
            "total_skills": len(self.skills),
            "loaded_skills": len(self.loaded_skills),
            "by_category": {
                cat.value: len([s for s in self.skills.values() if s.category == cat])
                for cat in SkillCategory
            },
            "total_tokens": sum(s.token_count for s in self.skills.values()),
        }

    def __repr__(self) -> str:
        return f"<ProceduralMemory skills={len(self.skills)} loaded={len(self.loaded_skills)}>"
