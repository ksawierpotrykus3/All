"""
CLI module for Extended Game Simulator.

**Validates: Requirements for CLI entry point, configuration loading, logging setup, and graceful shutdown**

Provides:
- Command-line argument parsing
- Configuration file loading and validation
- Logging setup (normal, verbose, headless modes)
- Graceful shutdown handling
"""

import argparse
import json
import logging
import signal
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class SimulatorCLI:
    """Command-line interface for the Extended Game Simulator."""

    # Valid variant presets
    VALID_VARIANTS = ['default', 'stress_test', 'hard_mode', 'custom']

    def __init__(self, argv: Optional[list] = None):
        """
        Initialize CLI parser.

        Args:
            argv: Command-line arguments (defaults to sys.argv[1:])
        """
        self.argv = argv or sys.argv[1:]
        self.parser = self._setup_parser()
        self.logger: Optional[logging.Logger] = None
        self.config: Optional[Dict[str, Any]] = None
        self.args: Optional[argparse.Namespace] = None

    def _setup_parser(self) -> argparse.ArgumentParser:
        """
        Configure CLI argument parser.

        Returns:
            Configured ArgumentParser
        """
        parser = argparse.ArgumentParser(
            description="Extended Game Simulator - Interactive testing framework",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s --help
  %(prog)s --config config.json --variant stress_test --iterations 50 --output ./reports
  %(prog)s --headless --verbose --iterations 100
            """
        )

        # Configuration
        parser.add_argument(
            '--config',
            type=str,
            default=None,
            help='Path to configuration JSON file (optional)'
        )

        # Variant preset
        parser.add_argument(
            '--variant',
            type=str,
            default='default',
            choices=self.VALID_VARIANTS,
            help='Variant preset to run (default: %(default)s)'
        )

        # Iteration count
        parser.add_argument(
            '--iterations',
            type=int,
            default=100,
            help='Number of iterations to run (default: %(default)s)'
        )

        # Output directory
        parser.add_argument(
            '--output',
            type=str,
            default='./reports',
            help='Directory for report output (default: %(default)s)'
        )

        # Session ID
        parser.add_argument(
            '--session-id',
            type=str,
            default=None,
            help='Custom session ID (default: auto-generated)'
        )

        # Logging level
        parser.add_argument(
            '--log-level',
            type=str,
            default='INFO',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            help='Logging level (default: %(default)s)'
        )

        # Headless mode (no UI)
        parser.add_argument(
            '--headless',
            action='store_true',
            help='Run without interactive UI'
        )

        # Verbose mode (sets log level to DEBUG)
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose (DEBUG) logging'
        )

        return parser

    def parse_args(self, argv: Optional[list] = None) -> argparse.Namespace:
        """
        Parse command-line arguments.

        Args:
            argv: Command-line arguments (defaults to self.argv)

        Returns:
            Parsed arguments namespace

        Raises:
            SystemExit: If arguments are invalid
        """
        argv = argv or self.argv
        self.args = self.parser.parse_args(argv)

        # Override log level if verbose is set
        if self.args.verbose:
            self.args.log_level = 'DEBUG'

        return self.args

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate loaded configuration.

        Args:
            config: Configuration dictionary

        Returns:
            True if valid, raises exception otherwise

        Raises:
            ValueError: If configuration is invalid
        """
        # Check required top-level keys
        if 'simulator' not in config:
            raise ValueError("Configuration missing required 'simulator' section")

        sim_config = config['simulator']

        # Validate iterations
        if 'iterations' in sim_config:
            iterations = sim_config['iterations']
            if not isinstance(iterations, int) or iterations <= 0:
                raise ValueError(f"Invalid iterations: must be positive integer, got {iterations}")

        # Validate variant
        if 'variant' in sim_config:
            variant = sim_config['variant']
            if variant not in self.VALID_VARIANTS:
                raise ValueError(f"Invalid variant '{variant}'. Must be one of: {self.VALID_VARIANTS}")

        return True

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from JSON file.

        Args:
            config_path: Path to configuration file

        Returns:
            Loaded configuration dictionary

        Raises:
            FileNotFoundError: If config file not found
            json.JSONDecodeError: If config file is invalid JSON
            ValueError: If configuration is invalid
        """
        path = Path(config_path)

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(path) as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in configuration file: {e.msg}",
                e.doc,
                e.pos
            )

        # Validate loaded configuration
        self.validate_config(config)

        self.config = config
        return config

    def setup_logging(self, args: argparse.Namespace) -> logging.Logger:
        """
        Configure logging based on CLI arguments.

        Args:
            args: Parsed CLI arguments

        Returns:
            Configured logger instance
        """
        # Determine log level
        log_level = logging.DEBUG if args.verbose else getattr(logging, args.log_level)

        # Create logs directory if needed
        logs_dir = Path('./logs')
        logs_dir.mkdir(exist_ok=True)

        # Generate log filename with timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_file = logs_dir / f'simulator_{timestamp}.log'

        # Configure logging
        log_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        log_formatter = logging.Formatter(log_format)

        # Create logger
        logger = logging.getLogger('simulator')
        logger.setLevel(log_level)

        # File handler (always enabled)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(log_formatter)
        logger.addHandler(file_handler)

        # Console handler (skip in headless mode)
        if not args.headless:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(log_formatter)
            logger.addHandler(console_handler)

        self.logger = logger
        logger.info(f"Simulator initialized: {timestamp}")
        logger.info(f"Configuration: variant={args.variant}, iterations={args.iterations}")
        logger.info(f"Logging level: {logging.getLevelName(log_level)}")
        logger.info(f"Output directory: {args.output}")

        return logger

    def setup_signal_handlers(self) -> None:
        """
        Setup graceful shutdown handlers for Ctrl+C and SIGTERM.
        """
        def signal_handler(signum, frame):
            if self.logger:
                self.logger.info(f"Received signal {signum}, shutting down gracefully...")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)    # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)   # SIGTERM

    def ensure_output_directory(self, output_path: str) -> Path:
        """
        Ensure output directory exists.

        Args:
            output_path: Path to output directory

        Returns:
            Path object for output directory

        Raises:
            OSError: If directory cannot be created
        """
        output_dir = Path(output_path)

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            if self.logger:
                self.logger.info(f"Output directory ready: {output_dir.absolute()}")
            return output_dir
        except OSError as e:
            error_msg = f"Failed to create output directory {output_path}: {e}"
            if self.logger:
                self.logger.error(error_msg)
            raise

    def run(self, argv: Optional[list] = None) -> int:
        """
        Execute simulator from CLI.

        Args:
            argv: Command-line arguments (defaults to self.argv)

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            # Parse arguments
            argv = argv or self.argv
            args = self.parse_args(argv)
            self.args = args

            # Setup logging
            logger = self.setup_logging(args)

            # Setup signal handlers for graceful shutdown
            self.setup_signal_handlers()

            # Load configuration if provided
            if args.config:
                try:
                    self.load_config(args.config)
                    logger.info(f"Loaded configuration from {args.config}")
                except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
                    logger.error(f"Configuration error: {e}")
                    return 1

            # Ensure output directory exists
            try:
                self.ensure_output_directory(args.output)
            except OSError as e:
                logger.error(f"Output directory error: {e}")
                return 1

            # Validate configuration
            try:
                if self.config:
                    self.validate_config(self.config)
            except ValueError as e:
                logger.error(f"Configuration validation error: {e}")
                return 1

            # Log execution parameters
            logger.info(f"Running with variant: {args.variant}")
            logger.info(f"Iterations: {args.iterations}")
            logger.info(f"Headless mode: {args.headless}")

            # Return success (caller will execute simulation)
            return 0

        except SystemExit as e:
            # Allow SystemExit from argparse --help to pass through
            return e.code if e.code else 0
        except Exception as e:
            if self.logger:
                self.logger.exception(f"Unexpected error: {e}")
            return 1


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    cli = SimulatorCLI(argv)
    return cli.run(argv)


if __name__ == '__main__':
    sys.exit(main())
