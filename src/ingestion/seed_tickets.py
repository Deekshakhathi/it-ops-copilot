"""Seed it_ops.db with realistic fictional incident tickets and index them into ChromaDB.

Run from the project root:
    python -m src.ingestion.seed_tickets

The script is idempotent: ticket titles are unique across the generated dataset,
and already-seeded titles are skipped, so running it again never inserts
duplicates, deletes data, or touches user-created tickets. ChromaDB indexing
uses upsert with ticket_id as the stable document ID, so re-running the script
cannot create duplicate vector entries.
"""
import random
from collections import Counter
from datetime import datetime, timedelta

from src.database.db import SessionLocal
from src.models.ticket import Ticket
from src.vector_store.chroma_db import collection, index_ticket

NOW = datetime.utcnow()
RNG = random.Random(42)

ASSIGNEES = [
    "Priya Sharma", "Alex Turner", "Maya Rodriguez", "Daniel Kim",
    "Sara Iqbal", "Tom Nowak", "Leila Haddad", "Chris Okafor",
    "Jing Wei", "Marcus Reed",
]

SCENARIOS = [
    {
        "category": "Database",
        "priority": "Critical",
        "servers": ["db-prod-01", "db-prod-02", "db-report-01"],
        "titles": [
            "Database connection pool exhausted",
            "Cannot connect to database - too many connections",
            "Database connection timeouts from application tier",
            "Primary database refusing new connections",
        ],
        "details": [
            "Monitoring shows pool saturation at 100% with client wait times above 30 seconds on the primary host.",
            "max_connections has been reached and the connection cache filled up after last night's report job.",
            "Application nodes report intermittent connection timeouts and rising 503 rates on write operations.",
            "The failover partner is up, but new client sessions are immediately rejected on the primary node.",
        ],
        "base": "{server} is rejecting incoming database sessions while application nodes log repeated connection failures.",
        "resolution": "Identified a connection leak in the reporting service that never released pooled sessions. Killed the stale connections, patched the leak, and enabled pool recycling. Saturation has stayed normal for 48 hours after remediation.",
    },
    {
        "category": "Application",
        "priority": "Critical",
        "servers": ["weblb-frontend-01", "web-app-03", "web-app-04"],
        "titles": [
            "Customer-facing website is completely down",
            "Checkout service returning 502 errors",
            "Landing page unavailable for customers",
            "Web tier returning HTTP 503 across regions",
        ],
        "details": [
            "Load balancer reports zero healthy upstreams in the web pool.",
            "Checkout calls are failing with upstream errors and abandoned carts are increasing rapidly.",
            "Edge nodes cannot reach the application pool; bounce rate is climbing in analytics.",
            "Health checks are failing on all four web nodes since the last rolling restart.",
        ],
        "base": "The public website is unreachable and monitoring shows HTTP 5xx responses for all customer traffic hitting {server}.",
        "resolution": "Rolled the web tier back after a broken configuration push replaced the upstream block. Restored the previous proxy configuration, relaunched the nodes, and confirmed a steady 200 response rate in monitoring. Added a pre-deploy configuration lint to the pipeline.",
    },
    {
        "category": "Performance",
        "priority": "High",
        "servers": ["web-app-01", "web-app-02", "api-core-01"],
        "titles": [
            "Admin dashboard loads taking over 15 seconds",
            "Search queries slow during peak business hours",
            "Monthly report generation extremely slow",
            "Page load times degraded after the latest release",
        ],
        "details": [
            "Profile traces show a full-table scan on the events table for every pane render.",
            "Query latency grows linearly with session concurrency between 10:00 and 12:00.",
            "Export jobs time out against the report cluster under full aggregation.",
            "New queries issue triple the previous number of round trips per page since release 4.8.",
        ],
        "base": "End users report severe slowness on core workflows, with application traces showing elevated response times originating near {server}.",
        "resolution": "Added covering indexes to the hot queries and capped per-request query fan-out in the release. Median response time dropped from 9.4 seconds to 0.8 seconds in APM tracing. Performance dashboard returned to green across all services.",
    },
    {
        "category": "Network",
        "priority": "High",
        "servers": ["core-sw-01", "edge-rtr-02", "vpn-gw-01"],
        "titles": [
            "Intermittent packet loss between datacenter zones",
            "VPN connection drops every few minutes",
            "Branch office users cannot reach the intranet",
            "High latency between app servers and auth backend",
        ],
        "details": [
            "Path monitoring records bursts of 8-12% packet loss between zone A and zone B every 20 minutes.",
            "IPsec tunnels renegotiate constantly and sessions reset under moderate load.",
            "The branch router drops its default route after ten minutes of uptime and traffic blackholes.",
            "Latency from the app tier to the authentication backend reached 400 ms, tripling login handshake times.",
        ],
        "base": "Network monitoring flags degraded connectivity around {server}, and users on the affected path report timeouts and dropped sessions.",
        "resolution": "Replaced a failing uplink transceiver and corrected a mismatched MTU on the inter-zone route. Packet loss cleared and latency returned to baseline. The fix was verified with continuous ping and path-monitoring baselines over a full week.",
    },
    {
        "category": "Infrastructure",
        "priority": "Critical",
        "servers": ["compute-node-07", "compute-node-11", "legacy-app-host-02"],
        "titles": [
            "Physical server unresponsive after power event",
            "Compute node rebooted unexpectedly",
            "Hardware failure suspected on legacy host",
            "Secondary application node offline after patching",
        ],
        "details": [
            "The out-of-band controller reports a brownout and the node has been down for two hours.",
            "Uptime reset without any maintenance window and kernel logs stop abruptly at 03:14.",
            "The host fails power-on self-test and the controller log shows a failing RAID adapter.",
            "The node never rejoined the fleet after security patching and health checks time out.",
        ],
        "base": "{server} is unreachable over SSH and shows as DOWN in fleet monitoring, reducing capacity for the workloads it hosts.",
        "resolution": "Datacenter engineers replaced the failed RAID controller and a power supply on the affected node. The host passed full self-test and rejoined the fleet with all services verified healthy. Post-incident review moved redundant workloads to a separate rack.",
    },
    {
        "category": "Infrastructure",
        "priority": "High",
        "servers": ["db-prod-03", "build-host-04", "fileshare-02"],
        "titles": [
            "Root filesystem 95% full on production host",
            "Log volume growing rapidly and filling the disk",
            "Disk pressure alert on the database host",
            "Out of disk errors appearing in application logs",
        ],
        "details": [
            "Cleanup window has not executed for six days, so rotated files piled up.",
            "Debug logging enabled by default in release 4.7 is writing gigabytes per hour.",
            "Archive log growth exceeds the weekly forecast and the volume sits at 97%.",
            "Workers crash on write failures and retries amplify the error rate further.",
        ],
        "base": "Disk utilization on {server} crossed the alert threshold and services risk read/write failures as the filesystem fills.",
        "resolution": "Purged rotated logs, re-enabled the cleanup job, and moved the write-ahead log directory to a dedicated larger volume. Disk usage stabilized around 60% and the alert cleared. Added disk growth forecasting to the weekly capacity review.",
    },
    {
        "category": "Performance",
        "priority": "High",
        "servers": ["web-app-05", "worker-pool-01", "api-core-02"],
        "titles": [
            "Worker processes killed by memory limits",
            "Out of memory terminations on application hosts",
            "Swap thrashing degrading response times",
            "Session cache memory leak after upgrade",
        ],
        "details": [
            "The kernel out-of-memory killer has terminated four workers in three hours.",
            "Resident memory grows monotonically until the container limit trips a restart.",
            "Free memory fell below 5% and swapping pushed request latency up 8x.",
            "Session objects accumulate after login instead of expiring on schedule.",
        ],
        "base": "Memory pressure on {server} is causing instability, with restarts and degraded service recurring through the day.",
        "resolution": "Patched the session store so expired entries are evicted, right-sized worker memory limits, and added memory growth alerting. Memory plateaued at a stable 62% with zero termination events over the following week. Restarts now occur only during scheduled maintenance.",
    },
    {
        "category": "Application",
        "priority": "Medium",
        "servers": ["auth-svc-01", "auth-svc-02"],
        "titles": [
            "Password reset emails not delivered",
            "Users cannot log in after SSO configuration change",
            "Login page returning intermittent 500 errors",
            "Two-factor prompts not appearing for new users",
        ],
        "details": [
            "The mail relay is dropping the reset template queue since 09:00.",
            "The metadata update changed the reply endpoint and broke federation trust.",
            "A race condition on session initialization throws null reference errors for some tenants.",
            "The enrollment flow skips factor registration when profile sync lags behind.",
        ],
        "base": "The authentication workflow around {server} is failing for affected users, blocking access to internal tools.",
        "resolution": "Corrected the relying-party reply URL and re-uploaded the federation metadata. Verified the full login and reset journey with test accounts across all tenants. The reset queue drained and user reports stopped within the hour.",
    },
    {
        "category": "Security",
        "priority": "High",
        "servers": ["auth-gw-01", "admin-portal-01", "workstation-zk12"],
        "titles": [
            "Suspicious login attempts from unusual region",
            "Brute force attempts detected against admin portal",
            "Malware alert quarantined on a workstation",
            "Unexpected outbound traffic flagged by inspection",
        ],
        "details": [
            "Forty failed logins for three accounts originated from a region with no prior activity.",
            "Rate limiting was bypassed via distributed source IPs at roughly 200 attempts per minute.",
            "Endpoint protection isolated a malicious binary and blocked its network callout.",
            "A host with no productive role pushed terabytes to an unknown external address overnight.",
        ],
        "base": "The security monitoring stack raised an alert tied to {server} that needs investigation and confirmed containment.",
        "resolution": "Blocked the source ranges, enforced lockout throttling on the admin portal, and rotated credentials for targeted accounts. The affected workstation was reimaged after forensic capture. No data exfiltration was confirmed with the network team.",
    },
    {
        "category": "Application",
        "priority": "High",
        "servers": ["api-gw-01", "api-pay-02", "webhook-svc-01"],
        "titles": [
            "Payment gateway timeouts during checkout",
            "Internal API 5xx error rate above threshold",
            "Partner integration returning rate limit errors",
            "Webhook deliveries failing to merchant endpoints",
        ],
        "details": [
            "The upstream provider is timing out on 12% of charge requests during peak load.",
            "A new endpoint skips the timeout wrapper and hangs until the gateway errors.",
            "The partner tightened quotas; our retry storm consumed the entire budget in minutes.",
            "A signing credential rotation restarted the service mid-batch and deliveries stalled in queue.",
        ],
        "base": "Errors around {server} are visible to downstream consumers, with retries masking the failure until queues back up.",
        "resolution": "Added bounded timeouts with exponential backoff and jittered retries, and aligned quota windows with the provider's documented limits. Gateway error rate fell from 14% to 0.3% and the backlog drained fully. Alert thresholds were retuned after the fix.",
    },
    {
        "category": "Database",
        "priority": "Medium",
        "servers": ["db-backup-01", "db-prod-04", "nas-backup-02"],
        "titles": [
            "Nightly backup job failed on database host",
            "Backup destination ran out of storage",
            "Incremental backups not completing on schedule",
            "Backup retention window consumed by stale snapshots",
        ],
        "details": [
            "The dump aborted at 03:00 with a lock timeout and produced no chainable set.",
            "Retention never pruned month-old images, filling the target volume.",
            "Change rate doubled after the feature launch, exceeding the transfer window.",
            "Automatic pruning was disabled during a migration toggle and never re-enabled.",
        ],
        "base": "The backup pipeline for {server} did not produce a verifiable restore point for last night.",
        "resolution": "Re-enabled retention pruning, resized the backup target, and split incremental jobs into two parallel streams. A test restore from the newest set passed checksum validation. Pipeline alerts now page the on-call engineer on any missed window.",
    },
    {
        "category": "Application",
        "priority": "Medium",
        "servers": ["cd-runner-03", "deploy-host-01", "registry-host-02"],
        "titles": [
            "Release rollout stuck at 40% of the fleet",
            "Deployment pipeline failing at the build step",
            "Canary deploy causing error spikes",
            "Rollback of the failed release incomplete",
        ],
        "details": [
            "Half the fleet is on the new release; the gate reads a stale metrics endpoint.",
            "The dependency mirror lost a pinned package and builds abort on a hash mismatch.",
            "The canary cohort shows a 6x error rate versus baseline on the new checkout path.",
            "Two nodes still serve the bad release because their drain hook times out.",
        ],
        "base": "The deployment workflow involving {server} halted mid-rollout and needs operator intervention to proceed or revert.",
        "resolution": "Fixed the metrics gate to read live endpoints, mirrored the missing package locally, and resumed the rollout wave by wave. Canary error rates returned to baseline before full promotion. The pipeline now snapshots prior state before any drain step.",
    },
    {
        "category": "Network",
        "priority": "Medium",
        "servers": ["dns-int-01", "dns-int-02", "proxy-edge-01"],
        "titles": [
            "Internal DNS resolution failures for service domain",
            "Stale DNS records pointing at decommissioned host",
            "Certificate renewal workflow silently failing",
            "Proxy misconfiguration returning 502 to clients",
        ],
        "details": [
            "The secondary resolver answers with failures for anything under the service zone.",
            "Cutover removed the old host, but its address record was never updated.",
            "The renewal automation lost its API credential and nobody owns the escalation path.",
            "A routing change put the backend in a different security group from the proxy fleet.",
        ],
        "base": "Name resolution and edge traffic handling around {server} is inconsistent, causing intermittent client-side failures.",
        "resolution": "Rebuilt the secondary resolver zone files from the primary, pruned stale records, and restored proxy-to-backend reachability in the security group. Resolution checks now pass for all service domains. Renewal automation runs nightly with failure alerts routed to the platform team.",
    },
    {
        "category": "Application",
        "priority": "High",
        "servers": ["cache-redis-01", "cache-redis-02"],
        "titles": [
            "Cache miss storm after failover",
            "Session store unavailable during failover test",
            "Cache eviction rate spiking abnormally",
            "Cache cluster restart causing login delays",
        ],
        "details": [
            "The failover promoted a cold replica and empty keys sent load to the database.",
            "Client libraries pin an old endpoint inside container images and never reconnect.",
            "Memory eviction hit an all-time high after hot keys landed on one shard.",
            "Clients piled tens of thousands of sessions onto a single node after a partial restart.",
        ],
        "base": "Cache behavior around {server} degraded abruptly, forcing heavy fallback traffic to the origin stores.",
        "resolution": "Pinned the client endpoint to the cluster address, re-warmed the cold shard, and rebalanced hot keys across nodes. Miss rate dropped from 55% back to the baseline of 4%. Failover testing was rerun successfully with pre-warmed standby replicas.",
    },
    {
        "category": "Performance",
        "priority": "Medium",
        "servers": ["queue-kafka-01", "queue-worker-04"],
        "titles": [
            "Event stream consumer lag rising sharply",
            "Background job backlog delaying notifications",
            "Message broker disk usage above high watermark",
            "Retry topic flooding after a schema mismatch",
        ],
        "details": [
            "Consumer group throughput halved after a partition rebalance at 02:00.",
            "The notification publisher emits 30x the expected volume on retries.",
            "Segments piled up when a consumer group went idle and retention lagged.",
            "A producer shipped records with an incompatible schema version and every record failed.",
        ],
        "base": "The event pipeline via {server} is falling behind, delaying downstream processing and user-facing notifications.",
        "resolution": "Fixed the schema registry version pin and drained the retry topic into the healthy consumer group. Lag fell from 2.1 million records to zero within the recovery window. Added per-group lag dashboards with paging thresholds for on-call coverage.",
    },
    {
        "category": "Other",
        "priority": "Medium",
        "servers": ["mail-relay-01", "mail-relay-02"],
        "titles": [
            "Outbound email queue backing up on relay",
            "Invoice emails delayed by several hours",
            "Mail relay rejecting large attachments",
            "Vendor mail rejected by spam filter rules",
        ],
        "details": [
            "The relay's connection pool to the upstream gateway is saturated since 08:00.",
            "Month-end batch reports grow the queue beyond processing capacity.",
            "An attachment size cap tightened last week now blocks legitimate finance mail.",
            "A filter reputation update started blocking the vendor's sending domain.",
        ],
        "base": "Mail flow through {server} is delayed or degraded for the affected senders and recipients.",
        "resolution": "Restored the approved attachment cap, whitelisted the vendor domain, and flushed the deferred queue in controlled batches. The backlog cleared and delivery times returned to under one minute. A follow-up ticket tracks a dedicated queue for bulk sends.",
    },
    {
        "category": "Infrastructure",
        "priority": "High",
        "servers": ["san-array-01", "db-prod-05", "storage-vol-07"],
        "titles": [
            "Storage I/O latency degraded on the SAN",
            "Volume performance dropped after migration",
            "Snapshot schedule causing I/O spikes",
            "Archive log filesystem slow to respond",
        ],
        "details": [
            "Read latency tripled to 40 ms after two shelves were re-cabled during maintenance.",
            "The volume landed on a tier with half the IOPS quota of the original.",
            "Snapshots of three large volumes now fire inside one ten-minute window.",
            "The archive log volume shares a controller with a hot backup host.",
        ],
        "base": "Storage subsystem behavior around {server} is causing application-level waits that surface as slow queries and timeouts.",
        "resolution": "Rebalanced shelves across both controllers, moved the volume to the high-IOPS tier, and staggered snapshots across the day. Latency returned to the 12 ms baseline and database wait events cleared. Capacity planning now includes controller load as a criterion.",
    },
    {
        "category": "Database",
        "priority": "High",
        "servers": ["db-replica-02", "db-replica-05", "db-prod-06"],
        "titles": [
            "Read replica lag exceeding ten minutes",
            "Replication stream broken on secondary",
            "Failover cluster state inconsistent between nodes",
            "Replication timeouts under heavy write load",
        ],
        "details": [
            "A long-running analytics query holds locks the apply stream needs to proceed.",
            "The secondary ran out of space for its transaction log and the stream stalled.",
            "Network flaps confused the cluster election and two nodes claim leadership.",
            "Bulk nightly imports saturate the link and the lag alarm never clears.",
        ],
        "base": "Replication for {server} is unhealthy, affecting read scalability and failover readiness.",
        "resolution": "Recovered the apply stream after freeing log space and moved the analytics workload to a dedicated replica. Cluster state was resynchronized through a controlled switchover. Failover drills now run monthly at a fixed maintenance window.",
    },
    {
        "category": "Security",
        "priority": "Critical",
        "servers": ["lb-public-01", "api-core-03", "cert-host-04"],
        "titles": [
            "Public API certificate expiring in five days",
            "Old certificate chain causing handshake failures",
            "Load balancer certificate renewal failed",
            "Mixed content warnings after certificate swap",
        ],
        "details": [
            "Automation missed the renewal window and the alert only fires at seven days out.",
            "Clients on older stacks reject the stronger intermediate chain pushed last week.",
            "The ACME challenge record never propagated and renewal attempts expired silently.",
            "Some templates still embed absolute resource URLs referencing the outdated scheme.",
        ],
        "base": "Certificate handling for {server} risks, or already causes, TLS errors for external consumers.",
        "resolution": "Completed renewal out-of-band without downtime and verified chain trust across client stacks. Fixed the ACME DNS automation and rebuilt asset URLs from relative paths. Certificate expiry monitoring moved to a 30-day threshold with paging.",
    },
    {
        "category": "Infrastructure",
        "priority": "Medium",
        "servers": ["lb-app-01", "lb-app-02"],
        "titles": [
            "Load balancer health checks failing on one node",
            "Session affinity broken after balancer upgrade",
            "Balancer connection table at capacity",
            "Weighted routing sending too much traffic to one host",
        ],
        "details": [
            "The node answers health checks only over IPv6 while the check uses IPv4.",
            "Sticky sessions reset because the cookie domain lost a rewrite rule in config.",
            "Connection use hit 98% of the table limit and new requests queue then drop.",
            "A typo in weights put 80% of traffic on the smallest instance.",
        ],
        "base": "Traffic distribution through the balancing tier is degraded, concentrating load and dropping client requests.",
        "resolution": "Corrected the weight configuration, restored the sticky domain rewrite, and enabled dual-stack health checks. Latency metrics normalized immediately and capacity was raised to match traffic. Configuration drift detection was queued with the change board.",
    },
    {
        "category": "Other",
        "priority": "Medium",
        "servers": ["monitoring-01", "monitoring-02"],
        "titles": [
            "Metrics pipeline stalled since early morning",
            "Disk threshold alerts not firing",
            "Log shipping delayed by 40 minutes",
            "Monitoring agent crashing on app hosts",
        ],
        "details": [
            "The collector's write buffer is full and no new points land in the dashboard.",
            "Alert rules reference a renamed metric that no longer exists.",
            "The log forwarder retries indefinitely against an unreachable intermediate sink.",
            "A library conflict introduced in a minor upgrade crashes the agent at startup.",
        ],
        "base": "Observability around {server} is compromised, so teams lack visibility while problems remain hidden.",
        "resolution": "Restarted the stalled collectors with an expanded write buffer, restored the metric names in alert rules, and fixed the log sink routing. Agent builds were rebuilt against the safe library set and redeployed. Coverage checks now pass across all host groups.",
    },
    {
        "category": "Infrastructure",
        "priority": "Medium",
        "servers": ["nfs-mnt-02", "fileshare-03", "fileshare-01"],
        "titles": [
            "NFS mount hanging on file servers",
            "Shared drives unavailable for the finance team",
            "Permission errors after shared storage migration",
            "File share serving stale cached files",
        ],
        "details": [
            "The mount stalls for a minute on metadata operations during opening hours.",
            "Finance users get access denied on folders they could open an hour ago.",
            "Migration copied ownership IDs that do not map cleanly into the destination domain.",
            "Cache invalidation broke during the cutover and files refresh only after reboot.",
        ],
        "base": "Shared storage access around {server} is degraded or incorrect, blocking daily work for several teams.",
        "resolution": "Rebound the export over the dedicated link, remapped ownership IDs in the destination domain, and cleared the cache on affected clients with a rolling reboot. Teams confirmed working access with their folder audits. User reports stopped the following day.",
    },
    {
        "category": "Infrastructure",
        "priority": "High",
        "servers": ["ctr-node-07", "ctr-node-09", "ctr-node-11"],
        "titles": [
            "Container pods evicted repeatedly on a node",
            "Containerized service crash-looping after update",
            "Cluster node marked unschedulable",
            "Pod image pull failing against the registry",
        ],
        "details": [
            "Evictions cluster on one node after a memory reservation was removed.",
            "A binary dependency changed at path level and the entrypoint aborts within seconds.",
            "The node's disk condition pushed the scheduler to exclude it from assignment.",
            "Registry credentials expired and every new launch times out pulling images.",
        ],
        "base": "Container platform health around {server} is degraded, and affected services cannot keep stable instances running.",
        "resolution": "Restored resource reservations and registry credentials, fixed the entrypoint path in the rebuilt image, and drained the failing node for repair. All services reconcile with zero crash loops since. Image pull health was added to the operational dashboards.",
    },
    {
        "category": "Database",
        "priority": "High",
        "servers": ["db-orders-01", "db-prod-07"],
        "titles": [
            "Deadlocks detected on the orders table",
            "Long-running query blocking writes for hours",
            "Stale reads reported after replica switchover",
            "Fragmented index slowing inventory scans",
        ],
        "details": [
            "Two scheduled batches lock the same rows in opposite order at 02:30.",
            "A missing index turned an ad-hoc report into a four-hour table scan.",
            "The switchover promoted a replica that lagged 40 seconds behind on writes.",
            "Bloat on the hottest index doubled scan costs under normal traffic.",
        ],
        "base": "Query coordination on {server} is misbehaving for the affected workloads and shows up as user-visible errors and delays.",
        "resolution": "Reordered batch updates to acquire locks consistently and added the missing index, clearing the blocking pattern in trace review. Stale reads were resolved with stricter read-after-write semantics. Post-fix monitoring shows lock resolution within milliseconds.",
    },
    {
        "category": "Application",
        "priority": "Medium",
        "servers": ["mobile-api-01", "push-gw-01"],
        "titles": [
            "iOS app crashing on startup in latest release",
            "Android push notifications not delivered",
            "Mobile API rejecting valid sessions",
            "App store reporting an elevated crash rate",
        ],
        "details": [
            "An unhandled empty-cache branch fires during cold start for users with saved sessions.",
            "The push gateway certificate pin list misses the new intermediate and delivery fails.",
            "Session refresh hits a token serializer that now rejects a legal character set.",
            "Crashes spike on mid-range devices while rendering the new image gallery.",
        ],
        "base": "Mobile clients connecting through {server} crash or misbehave for the affected release cohort.",
        "resolution": "Shipped a hotfix release that guards the cold-start path, refreshed the certificate pin set, and corrected the token serializer. Crash-free rate recovered from 97.1% to 99.8% across the fleet. Push delivery logs show sustained delivery at normal volumes.",
    },
    {
        "category": "Application",
        "priority": "Low",
        "servers": ["wiki-host-01", "staging-app-02"],
        "titles": [
            "Internal wiki search returning outdated results",
            "Staging environment shows last week's build",
            "Team calendar feed stale in the staff portal",
            "Archived release notes missing from knowledge base",
        ],
        "details": [
            "The search index stopped refreshing after the crawler job's schedule changed.",
            "The staging pipeline deploys to a slot that is not the one serving traffic.",
            "The calendar Connector cached feed until next month after a failed refresh.",
            "An export task skipped the archive section when the source changed names.",
        ],
        "base": "Content delivery from {server} is out of date for affected users, with no service outage.",
        "resolution": "Repointed the crawler schedule, corrected the slot targeting in the deploy script, and forced cache and index refreshes. Content is current again and a nightly freshness check was added. Remaining items were handled in routine maintenance.",
    },
    {
        "category": "Security",
        "priority": "Low",
        "servers": ["test-auth-01", "dev-net-05"],
        "titles": [
            "Quarterly credential rotation skipped for test systems",
            "Virus definitions out of date on two dev machines",
            "Unused admin accounts flagged by access review",
            "Phishing exercise completion rate below target",
        ],
        "details": [
            "Test environment rotation was dropped from the runbook during the reorg.",
            "Two machines have been offline during every scheduled definitions push.",
            "The review found five accounts with no logins for over 180 days.",
            "Only 61% of staff completed the last exercise against the 90% goal.",
        ],
        "base": "Routine security hygiene around {server} fell behind schedule and was reported by an automated compliance check.",
        "resolution": "Rotated all test system credentials, pushed updated definitions to the offline machines, and disabled the dormant accounts found during the review. A follow-up campaign lifted completion to 93%. The items were added as recurring tasks in the security calendar.",
    },
]

assert len(SCENARIOS) == 27 and all(len(s["titles"]) == 4 for s in SCENARIOS)


def build_specs():
    specs = []
    for index, scenario in enumerate(SCENARIOS):
        for variant, (title, detail) in enumerate(
            zip(scenario["titles"], scenario["details"])
        ):
            server = scenario["servers"][(index + variant) % len(scenario["servers"])]
            specs.append(
                {
                    "title": title,
                    "description": (
                        f"{scenario['base'].format(server=server)} {detail}"
                    ),
                    "category": scenario["category"],
                    "priority": scenario["priority"],
                    "affected_server": server,
                    "resolution": scenario["resolution"],
                }
            )
    return specs


def assign_status():
    roll = RNG.random()
    if roll < 0.14:
        return "Open"
    if roll < 0.34:
        return "In Progress"
    if roll < 0.62:
        return "Resolved"
    return "Closed"


def main():
    errors = []
    created = []
    specs = build_specs()

    session = SessionLocal()
    try:
        try:
            indexed_ids = set(collection.get(include=[]).get("ids", []))
        except Exception as exc:
            print(f"WARNING: could not read ChromaDB collection state: {exc}")
            indexed_ids = set()

        existing_titles = {title for (title,) in session.query(Ticket.title).all()}

        for spec in specs:
            if spec["title"] in existing_titles:
                continue

            last_ticket = session.query(Ticket).order_by(Ticket.id.desc()).first()
            max_id = 0 if last_ticket is None else last_ticket.id

            status = assign_status()
            created_at = NOW - timedelta(minutes=RNG.randint(30, 120 * 24 * 60))
            if status in ("Resolved", "Closed"):
                updated_at = min(
                    created_at + timedelta(minutes=RNG.randint(60, 72 * 60)),
                    NOW - timedelta(minutes=5),
                )
                resolution_notes = (
                    f"{spec['resolution']} Server involved: {spec['affected_server']}."
                )
            elif status == "In Progress":
                updated_at = created_at + timedelta(minutes=RNG.randint(30, 12 * 60))
                resolution_notes = None
            else:
                updated_at = created_at + timedelta(minutes=RNG.randint(0, 60))
                resolution_notes = None

            assignee = None
            if status != "Open" or spec["priority"] in ("High", "Critical"):
                assignee = RNG.choice(ASSIGNEES)

            ticket = Ticket(
                ticket_id=f"INC-{max_id + 1001}",
                title=spec["title"],
                description=spec["description"],
                category=spec["category"],
                priority=spec["priority"],
                status=status,
                affected_server=spec["affected_server"],
                assignee=assignee,
                resolution_notes=resolution_notes,
                created_at=created_at,
                updated_at=updated_at,
            )

            try:
                session.add(ticket)
                session.commit()
                session.refresh(ticket)
                created.append(ticket)
            except Exception as exc:
                session.rollback()
                errors.append(f"insert failed for '{spec['title']}': {exc}")

        indexed_now = 0
        for ticket in session.query(Ticket).all():
            if ticket.ticket_id in indexed_ids:
                continue
            try:
                index_ticket(ticket)
                indexed_ids.add(ticket.ticket_id)
                indexed_now += 1
            except Exception as exc:
                errors.append(f"chroma index failed for {ticket.ticket_id}: {exc}")

        total_in_db = session.query(Ticket).count()
        by_status = dict(Counter(t.status for t in session.query(Ticket).all()))
        by_priority = dict(Counter(t.priority for t in session.query(Ticket).all()))
        chroma_count = collection.count()
    finally:
        session.close()

    print()
    print("=" * 60)
    print("IT OPS COPILOT - SEEDING SUMMARY")
    print("=" * 60)
    print(f"Tickets created this run      : {len(created)}")
    print(f"Total tickets in SQLite       : {total_in_db}")
    print(f"Tickets indexed in ChromaDB   : {indexed_now} new "
          f"(collection total: {chroma_count})")
    print(f"Errors                        : {len(errors)}")

    print()
    print("Tickets by status:")
    for status, count in sorted(by_status.items()):
        print(f"  {status:<12}: {count}")

    print()
    print("Tickets by priority:")
    for priority, count in sorted(by_priority.items()):
        print(f"  {priority:<10}: {count}")

    if errors:
        print()
        print("Errors encountered:")
        for error in errors:
            print(f"  ERROR: {error}")

    print()
    print("Re-running this script is safe; already-seeded titles are skipped.")


if __name__ == "__main__":
    main()
