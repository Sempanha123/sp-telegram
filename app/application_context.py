from __future__ import annotations

from pathlib import Path

from app.controllers.account_controller import AccountController
from app.controllers.account_pool_controller import AccountPoolController
from app.controllers.alert_controller import AlertController
from app.controllers.blacklist_controller import BlacklistController
from app.controllers.campaign_controller import CampaignController
from app.controllers.dashboard_controller import DashboardController
from app.controllers.group_controller import GroupController
from app.controllers.job_controller import JobController
from app.controllers.log_controller import LogController
from app.controllers.member_controller import MemberController
from app.controllers.operations_controller import OperationsController
from app.controllers.restriction_controller import RestrictionController
from app.controllers.scheduler_controller import SchedulerController
from app.controllers.template_controller import TemplateController
from app.controllers.settings_controller import SettingsController
from app.controllers.license_controller import LicenseController
from app.database.database import DatabaseManager
from app.database.repositories.account_activity_repository import AccountActivityRepository
from app.database.repositories.account_repository import AccountRepository
from app.database.repositories.alert_repository import AlertRepository
from app.database.repositories.blacklist_repository import BlacklistRepository
from app.database.repositories.campaign_message_repository import CampaignMessageRepository
from app.database.repositories.campaign_repository import CampaignRepository
from app.database.repositories.campaign_target_repository import CampaignTargetRepository
from app.database.repositories.campaign_target_message_repository import CampaignTargetMessageRepository
from app.database.repositories.delivery_repository import DeliveryRepository
from app.database.repositories.rendered_message_repository import RenderedMessageRepository
from app.database.repositories.template_repository import TemplateRepository
from app.database.repositories.group_account_repository import GroupAccountRepository
from app.database.repositories.group_repository import GroupRepository
from app.database.repositories.job_repository import JobRepository
from app.database.repositories.job_attempt_repository import JobAttemptRepository
from app.database.repositories.recovery_event_repository import RecoveryEventRepository
from app.database.repositories.audit_repository import AuditRepository
from app.database.repositories.backup_repository import BackupRepository
from app.database.repositories.operation_event_repository import OperationEventRepository
from app.database.repositories.log_repository import LogRepository
from app.database.repositories.member_repository import MemberRepository
from app.database.repositories.member_source_repository import MemberSourceRepository
from app.database.repositories.member_exclusion_repository import MemberExclusionRepository
from app.database.repositories.member_target_repository import MemberTargetStateRepository
from app.database.repositories.member_target_action_repository import MemberTargetActionRepository
from app.database.repositories.account_member_repository import AccountMemberStateRepository
from app.database.repositories.member_sync_repository import MemberSyncRunRepository
from app.database.repositories.restriction_repository import RestrictionRepository
from app.database.repositories.schedule_repository import ScheduleRepository
from app.database.repositories.settings_repository import SettingsRepository
from app.database.repositories.telegram_session_repository import TelegramSessionRepository
from app.database.repositories.target_invite_link_repository import TargetInviteLinkRepository
from app.license.license_repository import LicenseRepository
from app.logging_config import AppLogger
from app.security.credential_store import CredentialStore
from app.security.session_security import SessionSecurity
from app.security.sensitive_data_filter import SensitiveDataFilter
from app.security.audit_security import AuditSecurity
from app.security.app_lock_service import AppLockService
from app.security.security_audit import SecurityAuditService
from app.license.device_manager import DeviceManager
from app.license.license_api import create_license_api
from app.license.license_service import LicenseService
from app.license.feature_gate import FeatureGate
from app.license.limit_service import LicenseLimitService, PlanUsageService
from app.services.account_service import AccountService
from app.services.account_pool_service import AccountPoolService
from app.services.account_safety_service import AccountSafetyService
from app.services.account_assignment_service import AccountAssignmentService
from app.services.alert_service import AlertService
from app.services.blacklist_service import BlacklistService
from app.services.campaign_service import CampaignService
from app.services.campaign_template_service import CampaignTemplateService
from app.services.dashboard_service import DashboardService
from app.services.group_service import GroupService
from app.services.job_service import JobService
from app.services.log_service import LogService
from app.services.member_service import MemberService
from app.services.member_pool_cleanup_service import MemberPoolCleanupService
from app.services.invitation_preflight_service import InvitationPreflightService
from app.services.target_invite_link_service import TargetInviteLinkService
from app.services.member_eligibility_service import MemberEligibilityEngine
from app.services.scheduler_service import SchedulerService
from app.services.settings_service import SettingsService
from app.services.telegram_account_service import TelegramAccountService
from app.services.telegram_config_service import TelegramConfigService
from app.telegram.auth_service import TelegramAuthService
from app.telegram.client_manager import TelegramClientManager
from app.telegram.session_pool import TelegramSessionPool
from app.telegram.health_service import TelegramAccountHealthService
from app.telegram.group_permission_service import TelegramGroupPermissionService
from app.telegram.group_resolver import TelegramGroupResolver
from app.telegram.group_discovery_service import TelegramGroupDiscoveryService
from app.telegram.group_sync_service import TelegramGroupSyncService
from app.telegram.invite_link_service import TelegramInviteLinkService
from app.telegram.group_service import TelegramGroupService
from app.telegram.profile_service import TelegramProfileService
from app.telegram.session_service import TelegramSessionService
from app.telegram.telegram_errors import TelegramErrorHandler
from app.telegram.media_service import TelegramMediaService
from app.telegram.messaging_service import TelegramMessagingService
from app.telegram.campaign_sender import CampaignSender
from app.telegram.campaign_preflight import CampaignPreflightService
from app.telegram.telegram_schedule_service import TelegramScheduleService
from app.telegram.member_normalizer import TelegramMemberNormalizer
from app.telegram.member_access_service import TelegramMemberAccessService
from app.telegram.member_sync_service import TelegramMemberSyncService
from app.telegram.member_target_service import TelegramTargetMembershipService
from app.telegram.target_invitation_service import TelegramTargetInvitationService
from app.telegram.member_service import TelegramMemberService
from app.telegram.workers.telegram_worker import TelegramWorkerThread
from app.utils.app_paths import AppPaths
from app.operations.worker_registry import WorkerRegistry
from app.operations.resource_locks import ResourceLockManager
from app.operations.network_monitor import NetworkMonitor
from app.operations.performance_monitor import PerformanceMonitor
from app.operations.alert_manager import AlertManager
from app.operations.restriction_manager import RestrictionManager
from app.operations.account_monitor import AccountMonitor
from app.operations.group_monitor import GroupMonitor
from app.operations.job_monitor import JobMonitor
from app.operations.recovery_manager import RecoveryManager
from app.operations.system_monitor import SystemMonitor
from app.operations.operations_manager import OperationsManager
from app.operations.maintenance_service import DatabaseMaintenanceService
from app.operations.backup_service import BackupService
from app.operations.diagnostics_service import DiagnosticsService
from app.operations.task_runner import OperationsTaskRunner
from app.operations.audit_service import AuditService
from app.operations.application_error_handler import ApplicationErrorHandler
from app.constants import WorkerState


class ApplicationContext:
    """Central dependency composition root for UI → controller → service → repository."""

    def __init__(self, project_root: str | Path | None = None, db_path: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
        self._closing = False
        self._closed = False
        self.paths = AppPaths.from_root(self.project_root)
        self.paths.ensure()
        self.data_dir = self.paths.data
        self.session_dir = self.paths.sessions

        self.database = DatabaseManager(db_path or self.paths.database)
        self.database.initialize()

        # Repositories
        self.account_repository = AccountRepository(self.database)
        self.restriction_repository = RestrictionRepository(self.database)
        self.activity_repository = AccountActivityRepository(self.database)
        self.group_repository = GroupRepository(self.database)
        self.group_account_repository = GroupAccountRepository(self.database)
        self.member_repository = MemberRepository(self.database)
        self.member_source_repository = MemberSourceRepository(self.database)
        self.member_exclusion_repository = MemberExclusionRepository(self.database)
        self.blacklist_repository = self.member_exclusion_repository
        self.member_target_repository = MemberTargetStateRepository(self.database)
        self.member_target_action_repository = MemberTargetActionRepository(self.database)
        self.account_member_repository = AccountMemberStateRepository(self.database)
        self.member_sync_repository = MemberSyncRunRepository(self.database)
        self.campaign_repository = CampaignRepository(self.database)
        self.campaign_target_repository = CampaignTargetRepository(self.database)
        self.campaign_message_repository = CampaignMessageRepository(self.database)
        self.campaign_target_message_repository = CampaignTargetMessageRepository(self.database)
        self.delivery_repository = DeliveryRepository(self.database)
        self.rendered_message_repository = RenderedMessageRepository(self.database)
        self.template_repository = TemplateRepository(self.database)
        self.schedule_repository = ScheduleRepository(self.database)
        self.job_repository = JobRepository(self.database)
        self.job_attempt_repository = JobAttemptRepository(self.database)
        self.recovery_event_repository = RecoveryEventRepository(self.database)
        self.audit_repository = AuditRepository(self.database)
        self.backup_repository = BackupRepository(self.database)
        self.operation_event_repository = OperationEventRepository(self.database)
        self.alert_repository = AlertRepository(self.database)
        self.log_repository = LogRepository(self.database)
        self.settings_repository = SettingsRepository(self.database)
        self.telegram_session_repository = TelegramSessionRepository(self.database)
        self.target_invite_link_repository = TargetInviteLinkRepository(self.database)
        self.license_repository = LicenseRepository(self.database)

        self.logger = AppLogger(self.paths.logs, self.log_repository)

        # Existing Phase 2 services
        self.account_service = AccountService(self.account_repository, self.activity_repository, self.restriction_repository)
        self.group_service = GroupService(self.group_repository, self.group_account_repository)
        self.blacklist_service = BlacklistService(self.blacklist_repository, self.member_repository, self.group_repository)
        self.job_service = JobService(self.job_repository, self.job_attempt_repository)
        self.alert_service = AlertService(self.alert_repository)
        self.log_service = LogService(self.log_repository)
        self.settings_service = SettingsService(self.settings_repository, self.database)
        self.account_safety_service = AccountSafetyService(
            self.database,
            str(self.settings_repository.get("default_timezone", "Asia/Phnom_Penh") or "Asia/Phnom_Penh"),
        )
        self.dashboard_service = DashboardService(
            self.account_repository, self.group_repository, self.member_repository,
            self.blacklist_repository, self.campaign_repository, self.job_repository, self.alert_repository,
        )

        # Phase 7 operational foundations are local-only and safe before Telegram starts.
        self.previous_shutdown_clean = bool(self.settings_repository.get("last_shutdown_clean", True))
        self.settings_repository.set("last_shutdown_clean", False)
        self.resource_locks = ResourceLockManager()
        self.worker_registry = WorkerRegistry()
        self.network_monitor = NetworkMonitor()
        self.sensitive_data_filter = SensitiveDataFilter(mask_phone=True, mask_ip=True, mask_session_path=True)
        self.audit_security = AuditSecurity(self.sensitive_data_filter)
        self.audit_service = AuditService(self.audit_repository, self.audit_security, self.logger)
        self.alert_manager = AlertManager(self.alert_repository, self.logger)
        self.restriction_manager = RestrictionManager(self.restriction_repository, self.account_repository, self.alert_manager, self.logger)
        self.account_monitor = AccountMonitor(self.account_repository, self.restriction_repository, self.alert_manager)
        self.group_monitor = GroupMonitor(self.group_repository, self.group_account_repository, self.alert_manager)
        self.performance_monitor = PerformanceMonitor(self.database, self.job_repository, self.worker_registry)
        self.job_monitor = JobMonitor(self.job_repository, self.job_attempt_repository, self.alert_manager, self.logger)
        self.recovery_manager = RecoveryManager(
            self.worker_registry, self.recovery_event_repository, self.alert_manager, self.resource_locks, self.database,
            max_restarts=int(self.settings_repository.get("max_worker_restarts", 3) or 3),
        )
        self.system_monitor = SystemMonitor(
            account_monitor=self.account_monitor, group_monitor=self.group_monitor, performance_monitor=self.performance_monitor,
            worker_registry=self.worker_registry, job_repository=self.job_repository, alert_repository=self.alert_repository, database=self.database,
        )
        self.operations_manager = OperationsManager(
            self.system_monitor, self.worker_registry, self.recovery_manager, self.restriction_manager,
            self.network_monitor, self.resource_locks, self.settings_service, self.logger,
        )
        self.maintenance_service = DatabaseMaintenanceService(
            self.database, log_repository=self.log_repository, alert_repository=self.alert_repository,
            job_repository=self.job_repository, resource_locks=self.resource_locks,
        )
        self.backup_service = BackupService(
            self.database, self.settings_repository, self.paths, self.backup_repository, self.audit_repository,
        )
        self.operations_task_runner = OperationsTaskRunner(max_workers=2)
        self.app_lock_service = AppLockService()
        self.error_handler = ApplicationErrorHandler(self.logger, self.alert_manager)

        # Phase 3 secure configuration + Telegram runtime.
        self.credential_store = CredentialStore()
        self.telegram_config_service = TelegramConfigService(self.credential_store)

        # Phase 8.2 license state is cached locally, while production entitlement
        # remains authoritative at the trusted license backend boundary.
        self.license_device_manager = DeviceManager(self.credential_store.storage, self.paths.data / "license_device_id")
        self.license_usage_service = PlanUsageService(
            self.account_repository, self.group_repository, self.member_repository, self.template_repository, self.license_repository,
        )
        self.license_api = create_license_api()
        self.license_service = LicenseService(
            self.license_repository, self.license_api, self.license_device_manager,
            usage_service=self.license_usage_service, audit_service=self.audit_service, alert_manager=self.alert_manager,
        )
        self.license_service.initialize()
        self.feature_gate = FeatureGate(self.license_service)
        self.license_limit_service = LicenseLimitService(self.license_service, self.license_usage_service)
        self.account_service.license_limit_service = self.license_limit_service
        self.telegram_error_handler = TelegramErrorHandler()
        self.session_security = SessionSecurity(self.session_dir)
        self.security_audit_service = SecurityAuditService(
            self.session_security, self.account_repository, self.telegram_config_service, self.paths, self.settings_service,
        )
        self.telegram_client_manager = TelegramClientManager(self.telegram_config_service)
        self.telegram_session_pool = TelegramSessionPool(
            self.telegram_client_manager, self.account_repository,
            max_active_clients=int(self.settings_repository.get("max_account_connections", 3) or 3),
        )
        self.account_assignment_service = AccountAssignmentService(self.account_repository, self.group_account_repository, self.job_repository)
        self.telegram_auth_service = TelegramAuthService(self.telegram_client_manager, self.telegram_error_handler)
        self.telegram_profile_service = TelegramProfileService(
            self.telegram_client_manager, session_pool=self.telegram_session_pool,
        )
        self.telegram_session_service = TelegramSessionService(self.telegram_client_manager)
        self.telegram_health_service = TelegramAccountHealthService(
            self.telegram_client_manager, self.telegram_profile_service, self.telegram_error_handler,
        )
        self.telegram_group_permission_service = TelegramGroupPermissionService(self.telegram_client_manager)
        self.telegram_group_resolver = TelegramGroupResolver(self.telegram_client_manager, self.telegram_group_permission_service)
        self.telegram_group_discovery_service = TelegramGroupDiscoveryService(self.telegram_client_manager, self.telegram_group_permission_service)
        self.telegram_group_sync_service = TelegramGroupSyncService(self.telegram_client_manager, self.telegram_group_permission_service)
        self.telegram_invite_link_service = TelegramInviteLinkService(self.telegram_client_manager, self.telegram_group_permission_service)
        self.target_invite_link_service = TargetInviteLinkService(
            self.group_repository, self.group_account_repository, self.account_repository,
            self.telegram_client_manager, self.telegram_invite_link_service, self.target_invite_link_repository,
            self.telegram_error_handler, session_pool=self.telegram_session_pool,
            account_service=self.account_service, alert_service=self.alert_service,
        )
        self.telegram_group_service = TelegramGroupService(
            self.telegram_group_resolver, self.telegram_group_discovery_service, self.telegram_group_permission_service,
            self.telegram_group_sync_service, self.telegram_invite_link_service,
        )
        self.telegram_member_normalizer = TelegramMemberNormalizer()
        self.telegram_member_access_service = TelegramMemberAccessService(self.telegram_client_manager, self.telegram_error_handler)
        self.telegram_member_sync_service = TelegramMemberSyncService(self.telegram_client_manager, self.telegram_member_normalizer, self.telegram_error_handler)
        self.telegram_target_membership_service = TelegramTargetMembershipService(self.telegram_client_manager, self.telegram_error_handler)
        self.telegram_target_invitation_service = TelegramTargetInvitationService(self.telegram_client_manager, self.telegram_error_handler)
        self.telegram_member_service = TelegramMemberService(self.telegram_member_access_service, self.telegram_member_sync_service, self.telegram_target_membership_service)
        self.member_eligibility_engine = MemberEligibilityEngine(self.member_repository, self.member_exclusion_repository, self.member_target_repository)
        self.invitation_preflight_service = InvitationPreflightService(
            self.member_repository, self.member_exclusion_repository, self.member_target_repository,
            self.group_repository, self.group_account_repository, self.account_repository,
            group_service=self.group_service, client_manager=self.telegram_client_manager,
            account_safety_service=self.account_safety_service,
        )
        self.member_service = MemberService(
            self.member_repository, self.member_source_repository, self.member_exclusion_repository, self.member_target_repository,
            self.account_member_repository, self.member_sync_repository, self.group_repository, self.group_account_repository,
            self.account_repository, self.telegram_member_service, self.member_eligibility_engine, self.job_repository,
            self.alert_service, self.logger, self.telegram_error_handler, self.telegram_client_manager, self.account_service,
            target_action_repository=self.member_target_action_repository, target_invitation_service=self.telegram_target_invitation_service,
            invitation_preflight_service=self.invitation_preflight_service,
        )
        self.member_service.account_safety_service = self.account_safety_service
        self.member_cleanup_service = MemberPoolCleanupService(self.member_repository, self.audit_repository)
        self.member_service.cleanup_service = self.member_cleanup_service
        self.member_service.account_assignment_service = self.account_assignment_service
        self.group_service.telegram = self.telegram_group_service
        self.group_service.target_invite_link_service = self.target_invite_link_service
        self.group_service.account_repository = self.account_repository
        self.group_service.client_manager = self.telegram_client_manager
        self.group_service.alerts = self.alert_service
        self.group_service.logger = self.logger
        self.group_service.jobs = self.job_repository
        self.group_service.error_handler = self.telegram_error_handler

        # Phase 6 authorized managed-group campaign runtime.
        self.telegram_media_service = TelegramMediaService(self.project_root)
        self.telegram_messaging_service = TelegramMessagingService(self.telegram_client_manager, self.telegram_error_handler)
        self.telegram_campaign_sender = CampaignSender(self.telegram_messaging_service, self.resource_locks)
        self.campaign_preflight_service = CampaignPreflightService(self.account_safety_service)
        self.telegram_schedule_service = TelegramScheduleService(self.telegram_client_manager, self.telegram_error_handler)
        self.campaign_service = CampaignService(
            self.campaign_repository, self.campaign_target_repository, self.campaign_message_repository,
            group_repository=self.group_repository, group_account_repository=self.group_account_repository,
            account_repository=self.account_repository, delivery_repository=self.delivery_repository,
            target_message_repository=self.campaign_target_message_repository,
            rendered_repository=self.rendered_message_repository, schedule_repository=self.schedule_repository,
            job_repository=self.job_repository, alert_repository=self.alert_repository, log_repository=self.log_repository,
            preflight_service=self.campaign_preflight_service, campaign_sender=self.telegram_campaign_sender,
            media_service=self.telegram_media_service, account_service=self.account_service,
        )
        self.campaign_service.account_assignment_service = self.account_assignment_service
        self.campaign_service.account_safety_service = self.account_safety_service
        self.scheduler_service = SchedulerService(
            self.schedule_repository, self.campaign_repository, campaign_service=self.campaign_service,
            telegram_schedule_service=self.telegram_schedule_service, target_repository=self.campaign_target_repository,
            delivery_repository=self.delivery_repository, group_repository=self.group_repository,
            job_repository=self.job_repository,
        )
        self.campaign_template_service = CampaignTemplateService(self.template_repository)

        self.telegram_account_service = TelegramAccountService(
            self.account_service,
            self.telegram_auth_service,
            self.telegram_profile_service,
            self.telegram_session_service,
            self.telegram_health_service,
            self.telegram_client_manager,
            self.telegram_error_handler,
            self.telegram_session_repository,
            self.alert_service,
            self.logger,
            self.telegram_config_service,
            self.session_dir,
            self.resource_locks,
        )
        self.telegram_worker = TelegramWorkerThread(self.telegram_client_manager)
        self.performance_monitor.telegram_queue_provider = lambda: self.telegram_worker.pending_count
        self.worker_registry.register("Telegram Worker", WorkerState.STARTING)
        self.telegram_worker.loopReady.connect(lambda: self.worker_registry.set_state("Telegram Worker", WorkerState.RUNNING))
        self.telegram_worker.heartbeat.connect(lambda: self.worker_registry.heartbeat("Telegram Worker"))
        self.telegram_worker.finished.connect(self._telegram_worker_finished)
        self.telegram_worker.start()
        for name, state in [
            ("Scheduler Worker", WorkerState.RUNNING), ("Job Worker", WorkerState.IDLE),
            ("Monitor Worker", WorkerState.IDLE), ("Database Maintenance Worker", WorkerState.IDLE),
            ("Notification Worker", WorkerState.IDLE),
        ]:
            self.worker_registry.register(name, state)
        self.recovery_manager.register_worker_restart("Telegram Worker", self.telegram_worker.restart_safely)

        # Avatar cache: downloads profile photos on the Telegram worker and
        # serves rounded pixmaps (with friendly initials fallbacks) to the UI.
        from app.services.avatar_service import AvatarService

        self.avatar_service = AvatarService(
            self.telegram_worker,
            self.telegram_profile_service,
            self.paths.data / "cache" / "avatars",
        )

        # Controllers
        self.account_pool_service = AccountPoolService(
            self.account_repository, self.group_account_repository, self.job_repository, self.restriction_repository,
            safety_service=self.account_safety_service,
        )
        self.account_pool_controller = AccountPoolController(self.account_pool_service)
        self.account_controller = AccountController(
            self.account_service, self.telegram_account_service, self.telegram_worker, self.settings_service,
        )
        self.account_controller.job_repository = self.job_repository
        # Retry pending avatar downloads as soon as their authorizing account
        # connects, so real profile photos appear without waiting for the timer.
        self.account_controller.accountConnected.connect(self.avatar_service.retry_for_account)
        self.group_controller = GroupController(self.group_service, self.telegram_worker, self.telegram_error_handler)
        self.account_controller.group_controller = self.group_controller
        self.member_controller = MemberController(self.member_service, self.blacklist_service, self.telegram_worker)
        self.blacklist_controller = BlacklistController(self.blacklist_service)
        self.campaign_controller = CampaignController(self.campaign_service, self.telegram_worker)
        self.scheduler_controller = SchedulerController(self.scheduler_service, self.telegram_worker)
        self.template_controller = TemplateController(self.campaign_template_service)
        self.job_controller = JobController(self.job_service)
        self.log_controller = LogController(self.log_service)
        self.alert_controller = AlertController(self.alert_service)
        self.settings_controller = SettingsController(
            self.settings_service, self.project_root, self.telegram_config_service, self.telegram_worker,
        )
        self.dashboard_controller = DashboardController(self.dashboard_service)
        self.restriction_controller = RestrictionController(
            self.restriction_repository, self.restriction_manager, self.account_controller,
        )
        self.diagnostics_service = DiagnosticsService(
            self, self.maintenance_service, self.worker_registry, self.performance_monitor, self.paths, self.sensitive_data_filter,
        )
        self.operations_controller = OperationsController(
            self.operations_manager, self.diagnostics_service, self.maintenance_service, self.backup_service,
            self.security_audit_service, self.operations_task_runner, self.app_lock_service, self.audit_repository,
        )
        self.license_controller = LicenseController(
            self.license_service, self.feature_gate, self.license_limit_service, self.telegram_worker,
        )
        # Central gates are injected once at the composition root; pages never
        # query plan definitions directly.
        self.account_controller.license_limit_service = self.license_limit_service
        self.account_controller.feature_gate = self.feature_gate
        self.telegram_account_service.feature_gate = self.feature_gate
        self.group_controller.license_limit_service = self.license_limit_service
        self.group_controller.feature_gate = self.feature_gate
        self.group_service.license_limit_service = self.license_limit_service
        self.group_service.feature_gate = self.feature_gate
        self.member_controller.feature_gate = self.feature_gate
        self.member_service.feature_gate = self.feature_gate
        self.member_service.license_limit_service = self.license_limit_service
        self.campaign_controller.feature_gate = self.feature_gate
        self.campaign_service.feature_gate = self.feature_gate
        self.template_controller.feature_gate = self.feature_gate
        self.template_controller.license_limit_service = self.license_limit_service
        self.campaign_template_service.feature_gate = self.feature_gate
        self.campaign_template_service.license_limit_service = self.license_limit_service
        self.scheduler_controller.feature_gate = self.feature_gate
        self.scheduler_service.feature_gate = self.feature_gate
        self.operations_controller.feature_gate = self.feature_gate
        self.operations_manager.feature_gate = self.feature_gate
        self.settings_controller.operations_controller = self.operations_controller
        self.settings_controller.app_lock_service = self.app_lock_service
        self.settings_controller.audit_service = self.audit_service
        self.operations_manager.register_component(
            "Campaign Sender", lambda: self.campaign_controller.set_operations_paused(True),
            lambda: self.campaign_controller.set_operations_paused(False),
        )
        self.operations_manager.register_component("Member Sync", self.member_controller.on_pause_sync, None)
        self.operations_manager.register_component("Group Sync", self.group_controller.cancel_bulk_sync, None)
        self.audit_service.wire_controllers(
            account=self.account_controller, group=self.group_controller, member=self.member_controller,
            campaign=self.campaign_controller, scheduler=self.scheduler_controller, settings=None,
        )

        # First-run defaults. QSettings remains for UI geometry/theme state only.
        if self.settings_repository.get("auto_connect_accounts", None) is None:
            self.settings_repository.set("auto_connect_accounts", False)
        if self.settings_repository.get("max_account_connections", None) is None:
            self.settings_repository.set("max_account_connections", 3)
        if self.settings_repository.get("auto_sync_groups", None) is None:
            self.settings_repository.set("auto_sync_groups", False)
        if self.settings_repository.get("group_sync_interval", None) is None:
            self.settings_repository.set("group_sync_interval", 60)
        if self.settings_repository.get("sync_group_permissions", None) is None:
            self.settings_repository.set("sync_group_permissions", True)
        if self.settings_repository.get("max_group_sync", None) is None:
            self.settings_repository.set("max_group_sync", 3)
        if self.settings_repository.get("default_timezone", None) is None:
            self.settings_repository.set("default_timezone", "Asia/Phnom_Penh")
        if self.settings_repository.get("default_parse_mode", None) is None:
            self.settings_repository.set("default_parse_mode", "PLAIN")
        if self.settings_repository.get("default_account_strategy", None) is None:
            self.settings_repository.set("default_account_strategy", "GROUP_PRIMARY")
        if self.settings_repository.get("missed_schedule_policy", None) is None:
            self.settings_repository.set("missed_schedule_policy", "ASK_ME")
        if self.settings_repository.get("require_campaign_preflight", None) is None:
            self.settings_repository.set("require_campaign_preflight", True)
        phase7_defaults = {
            "enable_account_monitor": True, "account_monitor_interval": 5,
            "enable_group_monitor": False, "group_monitor_interval": 30, "group_monitor_permissions": True,
            "monitor_scheduler": True, "monitor_workers": True,
            "auto_reconnect_network": True, "auto_restart_failed_workers": True,
            "max_worker_restarts": 3, "recovery_backoff_seconds": 15, "worker_heartbeat_stale_seconds": 60,
            "max_member_sync": 2, "max_campaign_workers": 2, "database_batch_size": 250,
            "log_retention_days": 90, "alert_retention_days": 90, "job_retention_days": 180,
            "auto_backup": False, "backup_frequency": "OFF", "backup_retention_count": 10,
            "backup_directory": str(self.paths.backups), "backup_sessions": False,
            "enable_app_lock": False, "app_lock_minutes": 10, "privacy_mode": False,
            "notify_critical_alerts": True, "notify_campaign_failures": True,
            "notify_login_required": True, "notify_backup_failure": True, "notify_successful_routine_jobs": False,
            "performance_sample_seconds": 10,
        }
        for key, value in phase7_defaults.items():
            if self.settings_repository.get(key, None) is None:
                self.settings_repository.set(key, value)
        self.settings_repository.set("session_path", str(self.session_dir))
        self.settings_repository.set("database_path", str(self.database.db_path))
        self.settings_repository.set("backup_path", str(self.paths.backups))
        self.app_lock_service.configure(
            bool(self.settings_repository.get("enable_app_lock", False)),
            int(self.settings_repository.get("app_lock_minutes", 10)),
        )
        self.startup_recovery_report = {"interrupted": 0, "reconcile_required": 0}
        if not self.previous_shutdown_clean:
            self.startup_recovery_report = self.job_monitor.recover_interrupted()
            total = self.startup_recovery_report["interrupted"] + self.startup_recovery_report["reconcile_required"]
            if total:
                self.alert_manager.raise_alert(
                    "WARNING", "UNCLEAN_SHUTDOWN", "SP Telegram recovered from an interrupted session",
                    f"{total} persisted job(s) require recovery or review.", dedupe_key="startup:unclean-shutdown",
                    source_type="SYSTEM", requires_action=bool(self.startup_recovery_report["reconcile_required"]), action_type="REVIEW_JOBS",
                )

        writable, message = self.telegram_account_service.validate_session_directory()
        if not writable:
            self.alert_service.create("CRITICAL", "SESSION_STORAGE", "Telegram session directory is not writable", message)
            self.logger.error("SECURITY", message, important=True, action="SESSION_DIRECTORY")
        self.session_directory_ok = writable
        storage = self.paths.validate()
        if storage.get("low_disk"):
            self.alert_manager.raise_alert("WARNING", "LOW_DISK_SPACE", "Application storage is running low", "Available disk space is below the configured safe startup threshold.", dedupe_key="storage:low-disk", source_type="SYSTEM")
        self.operations_manager.mark_ready()
        self.logger.info("SYSTEM", "Application context initialized.", important=True, action="STARTUP")

    def _telegram_worker_finished(self) -> None:
        if self._closing:
            self.worker_registry.set_state("Telegram Worker", WorkerState.STOPPED)
            return
        self.worker_registry.set_state("Telegram Worker", WorkerState.FAILED, "Telegram worker stopped unexpectedly.")
        self.alert_manager.raise_alert(
            "CRITICAL", "WORKER_FAILED", "Telegram worker stopped unexpectedly",
            "Safe automatic restart may be attempted if no protected write operation is in-flight.",
            dedupe_key="worker:telegram-failed", source_type="WORKER", source_id="Telegram Worker",
            requires_action=True, action_type="REVIEW_WORKER",
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closing = True
        self.operations_manager.begin_shutdown()
        self.logger.info("SYSTEM", "Telegram runtime shutting down.", action="SHUTDOWN")
        clean = False
        try:
            # Stop accepting local background maintenance before database close,
            # then stop the one long-lived Telegram QThread cooperatively.
            self.operations_task_runner.shutdown(wait=True)
            worker_stopped = self.telegram_worker.shutdown(self.telegram_account_service.shutdown())
            if not worker_stopped:
                raise RuntimeError("Telegram worker did not stop cleanly during application shutdown.")
            self.settings_repository.set("last_shutdown_clean", True)
            clean = True
        finally:
            if clean:
                self.logger.info("SYSTEM", "Application context closing cleanly.", important=True, action="SHUTDOWN")
            else:
                self.logger.error("SYSTEM", "Application context shutdown was incomplete.", important=True, action="SHUTDOWN")
            self.logger.close()
            self.database.close()
            self._closed = True
