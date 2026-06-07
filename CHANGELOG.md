# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.9.1] - 2026-06-07

### Fixed
- Plugin loading failure due to importing deprecated functions from interceptor.py
- Removed `has_execution_auth()` import and call
- Removed `grant_execution_auth()` import and call
- Removed `find_execution_plan()` import and call
- Removed `is_write_operation()` import and call

### Removed
- Layer 3 write operation interception (writes no longer require auth)
- Execution auth grant logic for L4 tasks

### Changed
- L4 tasks now wait for LLM to autonomously judge plan path
- Updated docstring with four-layer interception documentation

### Reference
- interceptor.py v5.8.0 removed these deprecated functions
- Layer 0: Sub-agent bypass
- Layer 1: Skill whitelist bypass
- Layer 2: Destructive command interception
- Layer 3: Workflow completion check (was Layer 4)

## [5.3.0] - 2026-05-19

### Added
- L4 enforcer module for strict execution control (enforcer.py)
- Enhanced context builder with +424 lines of improvements
- Optimized Ollama prompt with +151 lines (+8% token efficiency)
- Improved subagent detection mechanism

### Changed
- Strengthened L2/L3/L4 rules for better task classification
- Removed obsolete trigger_conditions.md (merged into l4.md)

### Fixed
- Better handling of edge cases in task level detection
- Improved context injection accuracy

## [5.2.1] - 2026-04-13

### Added
- Exported Git repository for open source distribution
- Added automated installation script (install.sh)
- Added comprehensive installation documentation (INSTALL.md)
- Added LICENSE file (MIT License)
- Added CHANGELOG.md following Keep a Changelog specification

### Changed
- Prepared project for GitHub release v5.2.1

## [5.1.0] - 2026-04-11

### Changed
- Removed obsolete state tracking mechanism (current_phase, phase_status, phase_action)
- Renamed L3 authentication to execution authentication (execution_auth)
- Simplified Hook logic - each message independently determines task level
- Removed dead code (_build_phase_info, bound_skills return values)
- Updated documentation to correct L3/L4 descriptions

## [5.0.0] - 2026-04-10

### Added
- Modular architecture refactoring (constants, workflow_cache, state, analyzer, context_builder, interceptor modules)
- Dynamic workflow detection (automatic loading of trigger words)

### Changed
- Workflow tasks no longer trigger L3 prompt injection
- Improved code organization and maintainability

## [4.0.0] - 2026-04-09

### Added
- L4 task level for complex project/planning tasks
- Planning documentation functionality

### Changed
- Removed circuit breaker mechanism to simplify architecture
- Fixed skill binding logic
- Improved task level detection and routing

## [1.0.0] - 2026-04-08

### Added
- Initial version
- Task level recognition (L0/L1/L2/L3)
- Write operation detection with warning context injection
- Dynamic rule loading based on task type
- Fallback mode for when Ollama is unavailable
- Skill binding based on task levels
- Migrated from OpenClaw handler.js (862 lines) to Hermes Plugin
- Support for both CLI and Gateway environments
- Pre-llm_call hook implementation in Python
