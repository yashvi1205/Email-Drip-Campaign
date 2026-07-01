#!/bin/bash
# ============================================================================
# AI Sales Team — Claude Code/Codex Skills Uninstaller
# Removes sales skills, Claude Code agents, scripts, and templates
# ============================================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    cat <<EOF
Usage: ./uninstall.sh [--target claude|codex|both]

Targets:
  claude  Remove from ~/.claude/skills and ~/.claude/agents (default)
  codex   Remove from ${CODEX_HOME:-~/.codex}/skills
  both    Remove from both Claude Code and Codex

Environment:
  AI_SALES_TARGET   Same as --target
  CLAUDE_HOME       Override Claude config directory (default: ~/.claude)
  CODEX_HOME        Override Codex config directory (default: ~/.codex)
EOF
}

TARGET="${AI_SALES_TARGET:-claude}"

while [ $# -gt 0 ]; do
    case "$1" in
        --target)
            if [ $# -lt 2 ]; then
                echo -e "${RED}Error: --target requires claude, codex, or both.${NC}"
                usage
                exit 1
            fi
            TARGET="$2"
            shift 2
            ;;
        --target=*)
            TARGET="${1#*=}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: unknown option '$1'.${NC}"
            usage
            exit 1
            ;;
    esac
done

case "$TARGET" in
    claude|codex|both) ;;
    *)
        echo -e "${RED}Error: target must be claude, codex, or both.${NC}"
        usage
        exit 1
        ;;
esac

CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

SKILLS=(
    sales
    sales-prospect
    sales-research
    sales-qualify
    sales-contacts
    sales-outreach
    sales-followup
    sales-prep
    sales-proposal
    sales-objections
    sales-icp
    sales-competitors
    sales-report
    sales-report-pdf
)

AGENTS=(
    sales-company
    sales-contacts
    sales-opportunity
    sales-competitive
    sales-strategy
)

remove_from_target() {
    local target_name="$1"
    local skills_dir="$2"
    local agents_dir="${3:-}"
    local remove_agents="${4:-false}"

    echo ""
    echo -e "${YELLOW}Uninstalling AI Sales Team for $target_name...${NC}"

    echo -e "${BLUE}Removing skills...${NC}"
    for skill in "${SKILLS[@]}"; do
        if [ -d "$skills_dir/$skill" ]; then
            rm -rf "$skills_dir/$skill"
            echo -e "  ${GREEN}✓${NC} Removed $skill"
        fi
    done

    if [ "$remove_agents" = "true" ]; then
        echo -e "${BLUE}Removing agents...${NC}"
        for agent in "${AGENTS[@]}"; do
            if [ -f "$agents_dir/$agent.md" ]; then
                rm -f "$agents_dir/$agent.md"
                echo -e "  ${GREEN}✓${NC} Removed $agent"
            fi
        done
    fi
}

if [ "$TARGET" = "claude" ] || [ "$TARGET" = "both" ]; then
    remove_from_target "Claude Code" "$CLAUDE_HOME/skills" "$CLAUDE_HOME/agents" "true"
fi

if [ "$TARGET" = "codex" ] || [ "$TARGET" = "both" ]; then
    remove_from_target "Codex" "$CODEX_HOME/skills" "" "false"
fi

echo ""
echo -e "${GREEN}AI Sales Team has been uninstalled for target: $TARGET.${NC}"
echo -e "Python packages (reportlab, beautifulsoup4) were not removed."
echo -e "To remove them: ${YELLOW}pip3 uninstall reportlab beautifulsoup4${NC}"
echo ""
