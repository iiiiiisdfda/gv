#ifndef GV_SIM_CMD_C
#define GV_SIM_CMD_C

#include "satCmd.h"

#include <cstdint>
#include <iomanip>
#include <fstream>
#include <stdexcept>

#include "gvMsg.h"

#include "minisatMgr.h"
#include "satMgr.h"
#include "util.h"

#include "iostream"

bool initSatCmd() {
    return (gvCmdMgr->regCmd("SATSolve DIMACS", 4, 6, new SatSolveDimacCmd));
}

using namespace gv::sat;

//----------------------------------------------------------------------
// EXPeriment
//----------------------------------------------------------------------
GVCmdExecStatus SatSolveDimacCmd::exec(const string& option) {
    //! Place your experimental functions and commands here
    vector<string> options;
    GVCmdExec::lexOptions(option, options);

    string filename;
    bool print_model = false;
    bool have_file = false;
    int64_t conflict_limit = -1;
    bool have_conflict_limit = false;
    bool static_decision_order = false;
    bool have_decision_order = false;
    int witness_lit = 0;
    bool have_witness = false;

    for (size_t i = 0; i < options.size();) {
        const string& tok = options[i];
        if (myStrNCmp("-File", tok, 2) == 0) {
            if (have_file)
                return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, tok);
            if (i + 1 >= options.size())
                return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, "-File");
            filename = options[i + 1];
            have_file = true;
            i += 2;
        } else if (myStrNCmp("-Model", tok, 2) == 0) {
            if (print_model)
                return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, tok);
            print_model = true;
            i += 1;
        } else if (myStrNCmp("-ConfLimit", tok, 2) == 0) {
            if (have_conflict_limit)
                return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, tok);
            if (i + 1 >= options.size())
                return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, "-ConfLimit");
            try {
                size_t idx = 0;
                conflict_limit = std::stoll(options[i + 1], &idx);
                if (idx != options[i + 1].size())
                    return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i + 1]);
            } catch (const std::logic_error&) {
                return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i + 1]);
            }
            if (conflict_limit < 0)
                return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i + 1]);
            have_conflict_limit = true;
            i += 2;
        } else if (myStrNCmp("-DecisionOrder", tok, 2) == 0) {
            if (have_decision_order)
                return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, tok);
            if (i + 1 >= options.size())
                return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, "-DecisionOrder");
            const string& mode = options[i + 1];
            if (myStrNCmp("VSIDS", mode, 2) == 0) {
                static_decision_order = false;
            } else if (myStrNCmp("STATIC", mode, 2) == 0) {
                static_decision_order = true;
            } else {
                return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, mode);
            }
            have_decision_order = true;
            i += 2;
        } else if (myStrNCmp("-Witness", tok, 2) == 0) {
            if (have_witness)
                return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, tok);
            if (i + 1 >= options.size())
                return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, "-Witness");
            try {
                size_t idx = 0;
                long lit = std::stol(options[i + 1], &idx);
                if (idx != options[i + 1].size() || lit == 0)
                    return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i + 1]);
                witness_lit = static_cast<int>(lit);
            } catch (const std::logic_error&) {
                return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i + 1]);
            }
            have_witness = true;
            i += 2;
        } else {
            return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, tok);
        }
    }

    if (!have_file)
        return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, "-File");

    ifstream file(filename);
    if (!file.is_open()) {
        gvMsg(GV_MSG_ERR) << "File " << filename << " does NOT Exist !!" << endl;
        return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, filename);
    }

    SatSolverMgr *gvSatSolver = new gv::sat::MinisatMgr();
    gvSatSolver->solve_dimacs_cnf(filename, print_model,
                                   have_conflict_limit ? conflict_limit : (int64_t)-1,
                                   static_decision_order,
                                   have_witness ? witness_lit : 0);

    return GV_CMD_EXEC_DONE;
}

void SatSolveDimacCmd::usage(const bool& verbose) const {
    gvMsg(GV_MSG_IFO)
        << "Usage: SATSolve DIMACS <-File <string(dimacsFormatFileName)>> [-Model] [-ConfLimit "
           "<int64>] [-DecisionOrder <VSIDS|STATIC>] [-Witness <non-zero-int-literal>]"
        << endl;
    if (verbose) {
        gvMsg(GV_MSG_IFO) << "       -Model      : If SAT, print DIMACS literals (one line)."
                          << endl;
        gvMsg(GV_MSG_IFO) << "       -ConfLimit N: Budget on total conflicts (MiniSat "
                             "stats.conflicts); may return UNKNOWN."
                          << endl;
        gvMsg(GV_MSG_IFO) << "       -DecisionOrder M: VSIDS (default) or STATIC." << endl;
        gvMsg(GV_MSG_IFO) << "       -Witness L   : If SAT, report assignment/truth of DIMACS "
                             "literal L (e.g., 3 or -7)."
                          << endl;
    }
}

void SatSolveDimacCmd::help() const {
    gvMsg(GV_MSG_IFO) << setw(20) << std::left << "SATSolve DIMACS: "
                      << "Command for satsolving DIMACS format file." << endl;
}

#endif
