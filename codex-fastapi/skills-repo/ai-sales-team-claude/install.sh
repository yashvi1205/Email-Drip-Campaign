#!/bin/bash
# ============================================================================
# AI Sales Team — Claude Code/Codex Skills Installer
# 14 Skills · 5 Agents · 5 Scripts · Schemas · PDF
# ============================================================================
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                              ║${NC}"
echo -e "${BLUE}║${NC}   ${CYAN}AI Sales Team — Claude Code / Codex Skills${NC}                ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}   ${GREEN}14 Skills · 5 Agents · 5 Scripts · Schemas · PDF${NC}                    ${BLUE}║${NC}"
echo -e "${BLUE}║                                                              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ---------------------------------------------------------------------------
# Detect script directory (handle both local and curl | bash)
# ---------------------------------------------------------------------------
GITHUB_REPO="zubair-trabzada/ai-sales-team-claude"
TEMP_DIR=""

if [ -n "${BASH_SOURCE[0]}" ] && [ "${BASH_SOURCE[0]}" != "bash" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "$SCRIPT_DIR/install.sh" ] && [ -d "$SCRIPT_DIR/skills" ]; then
        SOURCE_DIR="$SCRIPT_DIR"
        echo -e "${GREEN}Installing from local directory:${NC} $SOURCE_DIR"
    else
        SCRIPT_DIR=""
    fi
fi

if [ -z "${SCRIPT_DIR:-}" ] || [ ! -d "${SOURCE_DIR:-}" ]; then
    echo -e "${YELLOW}Cloning from GitHub...${NC}"
    TEMP_DIR=$(mktemp -d)
    if command -v git &>/dev/null; then
        git clone --depth 1 "https://github.com/$GITHUB_REPO.git" "$TEMP_DIR/repo" 2>/dev/null
        SOURCE_DIR="$TEMP_DIR/repo"
    else
        echo -e "${RED}Error: git is required for remote installation.${NC}"
        echo "Install git or run install.sh from a local clone."
        exit 1
    fi
    echo -e "${GREEN}Cloned successfully.${NC}"
fi

# ---------------------------------------------------------------------------
# Installer options
# ---------------------------------------------------------------------------
usage() {
    cat <<EOF
Usage: ./install.sh [--target claude|codex|both]

Targets:
  claude  Install to ~/.claude/skills and ~/.claude/agents (default)
  codex   Install to ${CODEX_HOME:-~/.codex}/skills
  both    Install to both Claude Code and Codex

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

install_for_target() {
    local target_name="$1"
    local skills_dir="$2"
    local agents_dir="${3:-}"
    local install_agents="${4:-false}"
    local install_count=0
    local agent_count=0
    local script_count=0
    local template_count=0
    local schema_count=0

    echo ""
    echo -e "${BLUE}Installing for $target_name...${NC}"

    echo -e "${BLUE}Creating directories...${NC}"
    mkdir -p "$skills_dir/sales/scripts"
    mkdir -p "$skills_dir/sales/templates"
    mkdir -p "$skills_dir/sales/schemas"
    echo -e "  ${GREEN}✓${NC} Skills directory ready: $skills_dir"

    if [ "$install_agents" = "true" ]; then
        mkdir -p "$agents_dir"
        echo -e "  ${GREEN}✓${NC} Agents directory ready: $agents_dir"
    fi

    echo -e "${BLUE}Installing skills...${NC}"

    if [ -f "$SOURCE_DIR/sales/SKILL.md" ]; then
        cp "$SOURCE_DIR/sales/SKILL.md" "$skills_dir/sales/SKILL.md"
        echo -e "  ${GREEN}✓${NC} sales (orchestrator)"
        install_count=$((install_count + 1))
    fi

    for skill in "${SKILLS[@]}"; do
        if [ -f "$SOURCE_DIR/skills/$skill/SKILL.md" ]; then
            mkdir -p "$skills_dir/$skill"
            cp "$SOURCE_DIR/skills/$skill/SKILL.md" "$skills_dir/$skill/SKILL.md"
            echo -e "  ${GREEN}✓${NC} $skill"
            install_count=$((install_count + 1))
        else
            echo -e "  ${YELLOW}⚠${NC} $skill (not found in source)"
        fi
    done

    if [ "$install_agents" = "true" ]; then
        echo -e "${BLUE}Installing agents...${NC}"

        for agent in "${AGENTS[@]}"; do
            if [ -f "$SOURCE_DIR/agents/$agent.md" ]; then
                cp "$SOURCE_DIR/agents/$agent.md" "$agents_dir/$agent.md"
                echo -e "  ${GREEN}✓${NC} $agent"
                agent_count=$((agent_count + 1))
            else
                echo -e "  ${YELLOW}⚠${NC} $agent (not found in source)"
            fi
        done
    else
        echo -e "${YELLOW}Skipping Claude Code agent files for $target_name.${NC}"
        echo -e "  ${YELLOW}⚠${NC} Codex loads skills from $skills_dir; Claude agent definitions are not installed."
    fi

    echo -e "${BLUE}Installing scripts...${NC}"

    for script in "$SOURCE_DIR"/scripts/*.py; do
        if [ -f "$script" ]; then
            cp "$script" "$skills_dir/sales/scripts/"
            echo -e "  ${GREEN}✓${NC} $(basename "$script")"
            script_count=$((script_count + 1))
        fi
    done

    echo -e "${BLUE}Installing templates...${NC}"

    for template in "$SOURCE_DIR"/templates/*.md; do
        if [ -f "$template" ]; then
            cp "$template" "$skills_dir/sales/templates/"
            echo -e "  ${GREEN}✓${NC} $(basename "$template")"
            template_count=$((template_count + 1))
        fi
    done

    echo -e "${BLUE}Installing schemas...${NC}"

    for schema in "$SOURCE_DIR"/schemas/*.json; do
        if [ -f "$schema" ]; then
            cp "$schema" "$skills_dir/sales/schemas/"
            echo -e "  ${GREEN}✓${NC} $(basename "$schema")"
            schema_count=$((schema_count + 1))
        fi
    done

    echo ""
    echo -e "  ${CYAN}$target_name Skills:${NC}    $install_count installed  →  $skills_dir"
    if [ "$install_agents" = "true" ]; then
        echo -e "  ${CYAN}$target_name Agents:${NC}    $agent_count installed  →  $agents_dir"
    fi
    echo -e "  ${CYAN}$target_name Scripts:${NC}   $script_count installed  →  $skills_dir/sales/scripts"
    echo -e "  ${CYAN}$target_name Templates:${NC} $template_count installed  →  $skills_dir/sales/templates"
    echo -e "  ${CYAN}$target_name Schemas:${NC}   $schema_count installed  →  $skills_dir/sales/schemas"
}

# ---------------------------------------------------------------------------
# Check for Claude Code / Codex
# ---------------------------------------------------------------------------
echo -e "${BLUE}Checking prerequisites...${NC}"
if [ "$TARGET" = "claude" ] || [ "$TARGET" = "both" ]; then
    if command -v claude &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Claude Code found"
    else
        echo -e "  ${YELLOW}⚠${NC} Claude Code CLI not found (skills will still be installed)"
    fi
fi

if [ "$TARGET" = "codex" ] || [ "$TARGET" = "both" ]; then
    if command -v codex &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Codex CLI found"
    else
        echo -e "  ${YELLOW}⚠${NC} Codex CLI not found (skills will still be installed)"
    fi
fi

if [ "$TARGET" = "claude" ] || [ "$TARGET" = "both" ]; then
    install_for_target "Claude Code" "$CLAUDE_HOME/skills" "$CLAUDE_HOME/agents" "true"
fi

if [ "$TARGET" = "codex" ] || [ "$TARGET" = "both" ]; then
    install_for_target "Codex" "$CODEX_HOME/skills" "" "false"
fi

# ---------------------------------------------------------------------------
# Check Python dependencies
# ---------------------------------------------------------------------------
echo -e "${BLUE}Checking Python environment...${NC}"

if command -v python3 &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Python 3 found: $(python3 --version 2>&1)"
else
    echo -e "  ${RED}✗${NC} Python 3 not found — required for scripts"
fi

# Check reportlab
if python3 -c "import reportlab" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} reportlab installed"
else
    echo -e "  ${YELLOW}⚠${NC} reportlab not installed (needed for PDF reports)"
    echo -e "      Install with: ${CYAN}pip3 install reportlab${NC}"
fi

# Check beautifulsoup4
if python3 -c "import bs4" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} beautifulsoup4 installed"
else
    echo -e "  ${YELLOW}⚠${NC} beautifulsoup4 not installed (optional, enhances parsing)"
    echo -e "      Install with: ${CYAN}pip3 install beautifulsoup4${NC}"
fi

if python3 -c "import pydantic" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} pydantic installed"
else
    echo -e "  ${YELLOW}⚠${NC} pydantic not installed (needed for sales-state.json validation)"
    echo -e "      Install with: ${CYAN}pip3 install pydantic${NC}"
fi

# ---------------------------------------------------------------------------
# Cleanup temp dir if used
# ---------------------------------------------------------------------------
if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
    echo -e "  ${GREEN}✓${NC} Cleaned up temporary files"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Installation Complete!                                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}Target:${NC} $TARGET"
echo ""

# ---------------------------------------------------------------------------
# Command reference
# ---------------------------------------------------------------------------
echo -e "${BLUE}Command Reference:${NC}"
echo ""
echo -e "  ${CYAN}/sales prospect <url>${NC}          Full prospect analysis (5 agents)"
echo -e "  ${CYAN}/sales quick <url>${NC}             60-second prospect snapshot"
echo -e "  ${CYAN}/sales research <url>${NC}          Deep company research"
echo -e "  ${CYAN}/sales qualify <url>${NC}           BANT + MEDDIC lead scoring"
echo -e "  ${CYAN}/sales contacts <url>${NC}          Find decision makers"
echo -e "  ${CYAN}/sales outreach <prospect>${NC}     Generate outreach sequences"
echo -e "  ${CYAN}/sales followup <prospect>${NC}     Create follow-up sequences"
echo -e "  ${CYAN}/sales prep <url>${NC}              Meeting preparation brief"
echo -e "  ${CYAN}/sales proposal <client>${NC}       Client proposal generation"
echo -e "  ${CYAN}/sales objections <topic>${NC}      Objection handling playbook"
echo -e "  ${CYAN}/sales icp <description>${NC}       Ideal Customer Profile builder"
echo -e "  ${CYAN}/sales competitors <url>${NC}       Competitive intelligence"
echo -e "  ${CYAN}/sales report${NC}                  Sales pipeline report (Markdown)"
echo -e "  ${CYAN}/sales report-pdf${NC}              Sales pipeline report (PDF)"
echo ""
echo -e "  ${YELLOW}Tip:${NC} Start with ${CYAN}/sales prospect <url>${NC} for a full analysis!"
echo ""
