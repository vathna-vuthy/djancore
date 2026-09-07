import time

from django.core.management.base import BaseCommand

from apps.notifications.services import NotificationService


class Command(BaseCommand):
    help = "Process and dispatch due scheduled notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--daemon",
            action="store_true",
            help="Run continuously in a background daemon loop.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=30,
            help="Poll interval in seconds when running in daemon mode (default: 30s).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Maximum notifications to process in one batch (default: 100).",
        )

    def handle(self, *args, **options):
        daemon = options["daemon"]
        interval = options["interval"]
        batch_size = options["batch_size"]

        if daemon:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting scheduled notification worker in daemon mode (poll interval: {interval}s)..."
                )
            )
            try:
                while True:
                    processed = NotificationService.process_due_notifications(
                        batch_size=batch_size
                    )
                    if processed > 0:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Successfully processed {processed} scheduled notifications."
                            )
                        )
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.WARNING("Scheduled notification worker stopped by user.")
                )
        else:
            processed = NotificationService.process_due_notifications(
                batch_size=batch_size
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processed {processed} due scheduled notifications."
                )
            )
