/****************************************************************************
  FileName     [ cirCmd.cpp ]
  PackageName  [ cir ]
  Synopsis     [ Define basic cir package commands ]
  Author       [ Chung-Yang (Ric) Huang ]
  Copyright    [ Copyright(c) 2023-present DVLab, GIEE, NTU, Taiwan ]
****************************************************************************/

#include "cirCmd.h"

#include <cassert>
#include <cctype>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <unordered_map>

#include "cirECO.h"
#include "cirGate.h"
#include "cirMgr.h"
#include "fmt/core.h"
#include "gvCmdMgr.h"
#include "gvType.h"
#include "util.h"
#include "yosysMgr.h"

using namespace std;

extern gv::cir::CirMgr* cirMgr;
extern int effLimit;

bool initCirCmd() {
    return (gvCmdMgr->regCmd("CIRRead", 4, new CirReadCmd) &&
            gvCmdMgr->regCmd("CIRPrint", 4, new CirPrintCmd) &&
            gvCmdMgr->regCmd("CIRGate", 4, new CirGateCmd) &&
            // gvCmdMgr->regCmd("CIRSWeep", 5, new CirSweepCmd) &&
            // gvCmdMgr->regCmd("CIROPTimize", 6, new CirOptCmd) &&
            // gvCmdMgr->regCmd("CIRSTRash", 6, new CirStrashCmd) &&
            // gvCmdMgr->regCmd("CIRSIMulate", 6, new CirSimCmd) &&
            // gvCmdMgr->regCmd("CIRFraig", 4, new CirFraigCmd) &&
            // gvCmdMgr->regCmd("CIRWrite", 4, new CirWriteCmd) &&
            // gvCmdMgr->regCmd("CIRMiter", 4, new CirMiterCmd) &&
            // gvCmdMgr->regCmd("CIREFFort", 6, new CirEffortCmd));
            gvCmdMgr->regCmd("CIRGate", 4, new CirGateCmd) &&
            gvCmdMgr->regCmd("CIRWrite", 4, new CirWriteCmd));
    // gvCmdMgr->regCmd("CIRBlast", 4, new CirBlastCmd));
}

enum CirCmdState {
    // Order matters! Do not change the order!!
    CIRINIT,
    CIRREAD,
    CIROPT,
    CIRSTRASH,
    CIRSIMULATE,
    // dummy end
    CIRCMDTOT
};

static CirCmdState curCmd = CIRINIT;

static gv::cir::BddOrderMode parseInputOrderMode(const string& token, bool& ok) {
    ok = true;
    if (myStrNCmp("-File", token, 2) == 0 || myStrNCmp("File", token, 2) == 0) return gv::cir::BDD_ORDER_FILE;
    if (myStrNCmp("-RFile", token, 3) == 0 || myStrNCmp("RFile", token, 3) == 0) return gv::cir::BDD_ORDER_RFILE;
    if (myStrNCmp("-DFS", token, 2) == 0 || myStrNCmp("DFS", token, 2) == 0) return gv::cir::BDD_ORDER_DFS;
    if (myStrNCmp("-RDFS", token, 3) == 0 || myStrNCmp("RDFS", token, 3) == 0) return gv::cir::BDD_ORDER_RDFS;
    ok = false;
    return gv::cir::BDD_ORDER_FILE;
}

static string trimSpaceLocal(const string& s) {
    size_t b = 0;
    while (b < s.size() && std::isspace(static_cast<unsigned char>(s[b]))) ++b;
    size_t e = s.size();
    while (e > b && std::isspace(static_cast<unsigned char>(s[e - 1]))) --e;
    return s.substr(b, e - b);
}

static bool isInputDeclLine(const string& line) {
    const string t = trimSpaceLocal(line);
    return (t.size() >= 6 && t.substr(0, 6) == "input ");
}

static string extractInputName(const string& line) {
    string s = trimSpaceLocal(line);
    if (s.empty()) return "";
    if (s.back() == ';') s.pop_back();
    // Take the last token as the signal name.
    stringstream ss(s);
    string token, last;
    while (ss >> token) last = token;
    if (last.empty() || last == "input") return "";
    if (!last.empty() && last.back() == ',') last.pop_back();
    return last;
}

static bool reorderVerilogInputDecls(const string& fileName, const vector<string>& piOrder) {
    ifstream in(fileName.c_str());
    if (!in) return false;
    vector<string> lines;
    string line;
    while (getline(in, line)) lines.push_back(line);
    in.close();

    unordered_map<string, string> inputDecl;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (!isInputDeclLine(lines[i])) continue;
        string name = extractInputName(lines[i]);
        if (!name.empty() && !inputDecl.count(name)) inputDecl[name] = lines[i];
    }
    if (inputDecl.empty()) return true;

    vector<string> orderedDecls;
    orderedDecls.reserve(inputDecl.size());
    unordered_map<string, bool> used;
    for (size_t i = 0; i < piOrder.size(); ++i) {
        auto it = inputDecl.find(piOrder[i]);
        if (it != inputDecl.end()) {
            orderedDecls.push_back(it->second);
            used[piOrder[i]] = true;
        }
    }
    for (auto it = inputDecl.begin(); it != inputDecl.end(); ++it) {
        if (!used[it->first]) orderedDecls.push_back(it->second);
    }

    vector<string> out;
    out.reserve(lines.size() + 4);
    bool inserted = false;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (isInputDeclLine(lines[i])) {
            if (!inserted) {
                for (size_t k = 0; k < orderedDecls.size(); ++k) out.push_back(orderedDecls[k]);
                inserted = true;
            }
            continue;
        }
        out.push_back(lines[i]);
    }

    ofstream of(fileName.c_str(), ios::out);
    if (!of) return false;
    for (size_t i = 0; i < out.size(); ++i) of << out[i] << "\n";
    return true;
}

//----------------------------------------------------------------------
//    CIRRead <-Verilog | -Aiger> <(string fileName)> [-Replace]
//----------------------------------------------------------------------
GVCmdExecStatus CirReadCmd::exec(const string& option) {
    // check option
    vector<string> options;
    GVCmdExec::lexOptions(option, options);
    FileType fileType = VERILOG;

    if (options.empty())
        return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, "");

    bool doReplace = false, fileError = false;
    string fileName = "", fileExt = "";
    for (size_t i = 0, n = options.size(); i < n; ++i) {
        if (myStrNCmp("-Replace", options[i], 2) == 0) {
            if (doReplace) return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, options[i]);
            doReplace = true;
        } else if (myStrNCmp("-Verilog", options[i], 2) == 0) {
            fileType = VERILOG;
        } else if (myStrNCmp("-Aiger", options[i], 2) == 0) {
            fileType = AIGER;
        } else {
            if (fileName.size())
                return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
            fileName = options[i];
            ifstream infile;
            infile.open(options[i].c_str());
            if (!infile)
                return GVCmdExec::errorOption(GV_CMD_OPT_FOPEN_FAIL, options[i]);
            infile.close();
        }
    }
    if (!fileName.empty()) {
        if (fileType == VERILOG) {
            fileExt   = fileName.substr(fileName.size() - 2);
            fileError = (fileExt != ".v");
        } else if (fileType == AIGER) {
            fileExt   = fileName.substr(fileName.size() - 4);
            fileError = (fileExt != ".aig");
        }
    } else fileError = true;

    if (fileError) return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, fileName);
    if (cirMgr != 0) {
        if (doReplace) {
            cout << "Note: original circuit is replaced..." << endl;
            curCmd = CIRINIT;
            delete cirMgr;
            cirMgr = 0;
        } else {
            cout << "Error: circuit already exists!!" << endl;
            return GV_CMD_EXEC_ERROR;
        }
    }

    cirMgr = new gv::cir::CirMgr();
    cirMgr->setFileName(fileName);
    cirMgr->setFileType(fileType);
    if (!cirMgr->readCircuitNew()) {
        delete cirMgr;
        cirMgr = 0;
        return GV_CMD_EXEC_NOP;
    }
    curCmd = CIRREAD;
    return GV_CMD_EXEC_DONE;
}

void CirReadCmd::usage(const bool& verbose) const {
    cout << "Usage: CIRRead <-Verilog | -Aiger> <(string fileName)> [-Replace]" << endl;
}

void CirReadCmd::help() const {
    cout << setw(20) << left << "CIRRead:"
         << "Read in a circuit and construct the netlist" << endl;
}

//----------------------------------------------------------------------
//    CIRPrint [-Summary | -Netlist | -PI | -PO]
//----------------------------------------------------------------------
GVCmdExecStatus
CirPrintCmd::exec(const string& option) {
    // check option
    string token;
    GVCmdExec::lexSingleOption(option, token);

    if (!cirMgr) {
        cout << "Error: circuit is not yet constructed!!" << endl;
        return GV_CMD_EXEC_ERROR;
    }
    if (token.empty() || myStrNCmp("-Summary", token, 2) == 0)
        cirMgr->printSummary();
    else if (myStrNCmp("-Netlist", token, 2) == 0)
        cirMgr->printNetlist();
    else if (myStrNCmp("-PI", token, 3) == 0)
        cirMgr->printPIs();
    else if (myStrNCmp("-PO", token, 3) == 0)
        cirMgr->printPOs();
    // else if (myStrNCmp("-FLoating", token, 3) == 0)
    //     cirMgr->printFloatGates();
    // else if (myStrNCmp("-FECpairs", token, 4) == 0)
    //     cirMgr->printFECPairs();
    else
        return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, token);

    return GV_CMD_EXEC_DONE;
}

void CirPrintCmd::usage(const bool& verbose) const {
    cout << "Usage: CIRPrint [-Summary | -Netlist | -PI | -PO]" << endl;
}

void CirPrintCmd::help() const {
    cout << setw(20) << left << "CIRPrint: "
         << "Print circuit" << endl;
}

//----------------------------------------------------------------------
//    CIRGate <<(int gateId)> [<-FANIn | -FANOut><(int level)>]>
//----------------------------------------------------------------------
GVCmdExecStatus
CirGateCmd::exec(const string& option) {
    if (!cirMgr) {
        cout << "Error: circuit has not been read!!" << endl;
        return GV_CMD_EXEC_ERROR;
    }

    // check option
    vector<string> options;
    GVCmdExec::lexOptions(option, options);

    if (options.empty())
        return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, "");

    int gateId = -1, level = 0;
    bool doFanin = false, doFanout = false;
    gv::cir::CirGate* thisGate = 0;
    for (size_t i = 0, n = options.size(); i < n; ++i) {
        bool checkLevel = false;
        if (myStrNCmp("-FANIn", options[i], 5) == 0) {
            if (doFanin || doFanout)
                return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
            doFanin    = true;
            checkLevel = true;
        } else if (myStrNCmp("-FANOut", options[i], 5) == 0) {
            if (doFanin || doFanout)
                return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
            doFanout   = true;
            checkLevel = true;
        } else if (!thisGate) {
            if (!myStr2Int(options[i], gateId) || gateId < 0)
                return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
            thisGate = cirMgr->getGate(gateId);
            if (!thisGate) {
                cout << "Error: Gate(" << gateId << ") not found!!" << endl;
                return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[0]);
            }
        } else if (thisGate)
            return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, options[i]);
        else
            return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
        if (checkLevel) {
            if (++i == n)
                return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, options[i - 1]);
            if (!myStr2Int(options[i], level) || level < 0)
                return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
            checkLevel = true;
        }
    }

    if (!thisGate) {
        cout << "Error: Gate id is not specified!!" << endl;
        return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, options.back());
    }

    if (doFanin)
        thisGate->reportFanin(level);
    else if (doFanout)
        thisGate->reportFanout(level);
    else
        thisGate->reportGate();

    return GV_CMD_EXEC_DONE;
}

void CirGateCmd::usage(const bool& verbose) const {
    cout << "Usage: CIRGate <<(int gateId)> [<-FANIn | -FANOut><(int level)>]>" << endl;
}

void CirGateCmd::help() const {
    cout << setw(20) << left << "CIRGate:"
         << "Report a gate" << endl;
}

//----------------------------------------------------------------------
//    CIRWrite <-Aag [(int gateId)] | -Aig | -Blif | -Verilog>
//             <-Output (string fileName)> [-InputOrder File|RFile|DFS|RDFS]
//----------------------------------------------------------------------
GVCmdExecStatus
CirWriteCmd::exec(const string& option) {
    if (!cirMgr) {
        cout << "Error: circuit is not yet constructed!!" << endl;
        return GV_CMD_EXEC_ERROR;
    }
    // check option
    vector<string> options;
    GVCmdExec::lexOptions(option, options);

    if (options.empty()) {
        cirMgr->writeAag(cout);
        return GV_CMD_EXEC_DONE;
    }
    FileType fileType;
    bool hasFile = false;
    bool hasInputOrder = false;
    gv::cir::BddOrderMode inputOrderMode = gv::cir::BDD_ORDER_FILE;
    int gateId;
    gv::cir::CirGate* thisGate = NULL;
    string outFileName;
    ofstream outfile;
    for (size_t i = 0, n = options.size(); i < n; ++i) {
        if (myStrNCmp("-Aiger", options[i], 2) == 0) {
            fileType = AIGER;
        } else if (myStrNCmp("-Aag", options[i], 2) == 0) {
            fileType = AAG;
        } else if (myStrNCmp("-Blif", options[i], 2) == 0) {
            fileType = BLIF;
        } else if (myStrNCmp("-Verilog", options[i], 2) == 0) {
            fileType = VERILOG;
        } else if (myStrNCmp("-Output", options[i], 2) == 0) {
            if (hasFile)
                return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, options[i]);
            if (++i == n)
                return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, options[i - 1]);
            outFileName = options[i].c_str();
            outfile.open(options[i].c_str(), ios::out);
            if (!outfile)
                return GVCmdExec::errorOption(GV_CMD_OPT_FOPEN_FAIL, options[1]);
            hasFile = true;
            cirMgr->setFileName(outFileName);
        } else if (myStrNCmp("-InputOrder", options[i], 3) == 0) {
            if (hasInputOrder) return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, options[i]);
            if (++i == n) return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, options[i - 1]);
            bool ok = false;
            inputOrderMode = parseInputOrderMode(options[i], ok);
            if (!ok) return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
            hasInputOrder = true;
        } else if (myStr2Int(options[i], gateId) && gateId >= 0) {
            if (fileType != AAG)
                return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, options[i]);
            if (thisGate != NULL)
                return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, options[i]);
            thisGate = cirMgr->getGate(gateId);
            if (!thisGate) {
                cout << "Error: Gate(" << gateId << ") not found!!" << endl;
                return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
            }
            if (!thisGate->isAig()) {
                cout << "Error: Gate(" << gateId << ") is NOT an AIG!!" << endl;
                return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
            }
        } else return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
    }

    if (!hasFile) return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, "-Output");

    // cout << outFileName << "\n";
    // TODO: Fix the CIRWRITE command with the new functions
    if (fileType == AIGER) {
        cirMgr->getYosysMgr()->writeAiger(outFileName);
    } else if (fileType == BLIF) {
        // Optional: support BLIF flow via Yosys
        cirMgr->getYosysMgr()->writeBlif(outFileName);
    } else if (fileType == VERILOG) {
        cirMgr->getYosysMgr()->writeVerilog(outFileName);
        vector<gv::cir::CirPiGate*> order = cirMgr->collectPiOrder(inputOrderMode);
        vector<string> piNames;
        piNames.reserve(order.size());
        for (size_t i = 0; i < order.size(); ++i) {
            char* n = order[i]->getName();
            if (n && *n) piNames.push_back(string(n));
        }
        if (!reorderVerilogInputDecls(outFileName, piNames))
            return GVCmdExec::errorOption(GV_CMD_OPT_FOPEN_FAIL, outFileName);
    } else if (fileType == AAG) {
        // ASCII AAG output using CirMgr's native writer
        if (!thisGate) {
            assert(hasFile);
            cirMgr->writeAag(outfile);
        } else if (hasFile)
            cirMgr->writeGate(outfile, thisGate);
        else
            cirMgr->writeGate(cout, thisGate);
    }
    return GV_CMD_EXEC_DONE;
}

void CirWriteCmd::usage(const bool& verbose) const {
    cout << "Usage: CIRWrite <-Aag [(int gateId)] | -Aig | -Blif | -Verilog>"
         << " <-Output (string fileName)> [-InputOrder File|RFile|DFS|RDFS]" << endl;
}

void CirWriteCmd::help() const {
    cout << setw(20) << left << "CIRWrite: "
         << "Write the netlist to an AIG/AAG/BLIF/Verilog file\n";
}

// void
// CirSweepCmd::help() const
// {
//    cout << setw(15) << left << "CIRSWeep: "
//         << "remove unused gates\n";
// }

// //----------------------------------------------------------------------
// //    CIROPTimize
// //----------------------------------------------------------------------
// GVCmdExecStatus
// CirOptCmd::exec(const string& option)
// {
//    if (!cirMgr) {
//       cout << "Error: circuit is not yet constructed!!" << endl;
//       return GV_CMD_EXEC_ERROR;
//    }
//    // check option
//    vector<string> options;
//    GVCmdExec::lexOptions(option, options);

//    if (!options.empty())
//       return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, options[0]);

//    assert(curCmd != CIRINIT);
//    if (curCmd == CIRSIMULATE) {
//       cout << "Error: circuit has been simulated!! Do \"CIRFraig\" first!!"
//            << endl;
//       return GV_CMD_EXEC_ERROR;
//    }
//    cirMgr->optimize();
//    curCmd = CIROPT;

//    return GV_CMD_EXEC_DONE;
// }

// void
// CirOptCmd::usage(const bool& verbose) const
// {
//    cout << "Usage: CIROPTimize" << endl;
// }

// void
// CirOptCmd::help() const
// {
//    cout << setw(15) << left << "CIROPTimize: "
//         << "perform trivial optimizations\n";
// }

// //----------------------------------------------------------------------
// //    CIRSTRash
// //----------------------------------------------------------------------
// GVCmdExecStatus
// CirStrashCmd::exec(const string& option)
// {
//    if (!cirMgr) {
//       cout << "Error: circuit is not yet constructed!!" << endl;
//       return GV_CMD_EXEC_ERROR;
//    }
//    // check option
//    vector<string> options;
//    GVCmdExec::lexOptions(option, options);

//    if (!options.empty())
//       return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, options[0]);

//    assert(curCmd != CIRINIT);
//    if (curCmd == CIRSTRASH) {
//       cout << "Error: circuit has been strashed!!" << endl;
//       return GV_CMD_EXEC_ERROR;
//    }
//    else if (curCmd == CIRSIMULATE) {
//       cout << "Error: circuit has been simulated!! Do \"CIRFraig\" first!!"
//            << endl;
//       return GV_CMD_EXEC_ERROR;
//    }
//    cirMgr->strash();
//    curCmd = CIRSTRASH;

//    return GV_CMD_EXEC_DONE;
// }

// void
// CirStrashCmd::usage(const bool& verbose) const
// {
//    cout << "Usage: CIRSTRash" << endl;
// }

// void
// CirStrashCmd::help() const
// {
//    cout << setw(15) << left << "CIRSTRash: "
//         << "perform structural hash on the circuit netlist\n";
// }

//----------------------------------------------------------------------
//    CIRSIMulate <-Random | -File <string patternFile>>
//                [-Output (string logFile)]
//----------------------------------------------------------------------
// GVCmdExecStatus
// CirSimCmd::exec(const string& option) {
//     if (!cirMgr) {
//         cout << "Error: circuit is not yet constructed!!" << endl;
//         return GV_CMD_EXEC_ERROR;
//     }
//     // check option
//     vector<string> options;
//     GVCmdExec::lexOptions(option, options);

//     ifstream patternFile;
//     ofstream logFile;
//     bool doRandom = false, doFile = false, doLog = false;
//     for (size_t i = 0, n = options.size(); i < n; ++i) {
//         if (myStrNCmp("-Random", options[i], 2) == 0) {
//             if (doRandom || doFile)
//                 return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
//             doRandom = true;
//         } else if (myStrNCmp("-File", options[i], 2) == 0) {
//             if (doRandom || doFile)
//                 return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
//             if (++i == n)
//                 return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, options[i - 1]);
//             patternFile.open(options[i].c_str(), ios::in);
//             if (!patternFile)
//                 return GVCmdExec::errorOption(GV_CMD_OPT_FOPEN_FAIL, options[i]);
//             doFile = true;
//         } else if (myStrNCmp("-Output", options[i], 2) == 0) {
//             if (doLog)
//                 return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
//             if (++i == n)
//                 return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, options[i - 1]);
//             logFile.open(options[i].c_str(), ios::out);
//             if (!logFile)
//                 return GVCmdExec::errorOption(GV_CMD_OPT_FOPEN_FAIL, options[i]);
//             doLog = true;
//         } else
//             return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
//     }

//     if (!doRandom && !doFile)
//         return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, "");

//     assert(curCmd != CIRINIT);
//     if (doLog)
//         cirMgr->setSimLog(&logFile);
//     else cirMgr->setSimLog(0);

//     if (doRandom)
//         cirMgr->randomSim();
//     else
//         cirMgr->fileSim(patternFile);
//     cirMgr->setSimLog(0);
//     curCmd = CIRSIMULATE;

//     return GV_CMD_EXEC_DONE;
// }

// void CirSimCmd::usage(const bool& verbose) const {
//     cout << "Usage: CIRSIMulate <-Random | -File <string patternFile>>\n"
//          << "                   [-Output (string logFile)]" << endl;
// }

// void CirSimCmd::help() const {
//     cout << setw(20) << left << "CIRSIMulate: "
//          << "Perform Boolean logic simulation on the circuit\n";
// }

// ----------------------------------------------------------------------
// CIRBlast
// ----------------------------------------------------------------------
// GVCmdExecStatus
// CirBlastCmd::exec(const string& option) {
//     // check option
//     vector<string> options;
//     GVCmdExec::lexOptions(option, options);
//     string fileName   = cirMgr->getFileName();
//     FileType fileType = cirMgr->getFileType();
//     if (!cirMgr->readCirFromAbc(fileName, fileType)) {
//         delete cirMgr;
//         cirMgr = 0;
//     }

//     return GV_CMD_EXEC_DONE;
// }

// void CirBlastCmd::usage(const bool& verbose) const {
//     cout << "Usage: CIRBlast" << endl;
// }

// void CirBlastCmd::help() const {
//     cout << setw(20) << left << "CIRBlast:"
//          << "Convert network to AIG." << endl;
// }
// //----------------------------------------------------------------------
// //    CIRFraig
// //----------------------------------------------------------------------
// GVCmdExecStatus
// CirFraigCmd::exec(const string& option)
// {
//    if (!cirMgr) {
//       cout << "Error: circuit is not yet constructed!!" << endl;
//       return GV_CMD_EXEC_ERROR;
//    }
//    // check option
//    vector<string> options;
//    GVCmdExec::lexOptions(option, options);

//    if (!options.empty())
//       return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, options[0]);

//    if (curCmd != CIRSIMULATE) {
//       cout << "Error: circuit is not yet simulated!!" << endl;
//       return GV_CMD_EXEC_ERROR;
//    }
//    cirMgr->fraig();
//    curCmd = CIRFRAIG;

//    return GV_CMD_EXEC_DONE;
// }

// void
// CirFraigCmd::usage(const bool& verbose) const
// {
//    cout << "Usage: CIRFraig" << endl;
// }

// void
// CirFraigCmd::help() const
// {
//    cout << setw(15) << left << "CIRFraig: "
//         << "perform Boolean logic simulation on the circuit\n";
// }

// //----------------------------------------------------------------------
// //    CIRWrite [(int gateId)][-Output (string aagFile)]
// //----------------------------------------------------------------------
// GVCmdExecStatus
// CirWriteCmd::exec(const string& option)
// {
//    if (!cirMgr) {
//       cout << "Error: circuit is not yet constructed!!" << endl;
//       return GV_CMD_EXEC_ERROR;
//    }
//    // check option
//    vector<string> options;
//    GVCmdExec::lexOptions(option, options);

//    if (options.empty()) {
//       cirMgr->writeAag(cout);
//       return GV_CMD_EXEC_DONE;
//    }
//    bool hasFile = false;
//    int gateId;
//    CirGate *thisGate = NULL;
//    ofstream outfile;
//    for (size_t i = 0, n = options.size(); i < n; ++i) {
//       if (myStrNCmp("-Output", options[i], 2) == 0) {
//          if (hasFile)
//             return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, options[i]);
//          if (++i == n)
//             return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, options[i-1]);
//          outfile.open(options[i].c_str(), ios::out);
//          if (!outfile)
//             return GVCmdExec::errorOption(GV_CMD_OPT_FOPEN_FAIL, options[1]);
//          hasFile = true;
//       }
//       else if (myStr2Int(options[i], gateId) && gateId >= 0) {
//          if (thisGate != NULL)
//             return GVCmdExec::errorOption(GV_CMD_OPT_EXTRA, options[i]);
//          thisGate = cirMgr->getGate(gateId);
//          if (!thisGate) {
//             cout << "Error: Gate(" << gateId << ") not found!!" << endl;
//             return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
//          }
//          if (!thisGate->isAig()) {
//              cout << "Error: Gate(" << gateId << ") is NOT an AIG!!" << endl;
//             return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
//          }
//       }
//       else return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, options[i]);
//    }

//    if (!thisGate) {
//       assert (hasFile);
//       cirMgr->writeAag(outfile);
//    }
//    else if (hasFile) cirMgr->writeGate(outfile, thisGate);
//    else cirMgr->writeGate(cout, thisGate);

//    return GV_CMD_EXEC_DONE;
// }

// void
// CirWriteCmd::usage(const bool& verbose) const
// {
//    cout << "Usage: CIRWrite [(int gateId)][-Output (string aagFile)]" << endl;
// }

// void
// CirWriteCmd::help() const
// {
//    cout << setw(15) << left << "CIRWrite: "
//         << "write the netlist to an ASCII AIG file (.aag)\n";
// }

// //----------------------------------------------------------------------
// //    CIRMiter <(string inFile1)> <(string inFile2)>
// //----------------------------------------------------------------------
// GVCmdExecStatus
// CirMiterCmd::exec(const string& option)
// {
//    // check option
//    vector<string> options;
//    GVCmdExec::lexOptions(option, options);

//    if (cirMgr != 0) {
//       cout << "Note: original circuit is replaced..." << endl;
//       curCmd = CIRINIT;
//       delete cirMgr; cirMgr = 0;
//    }
//    CirMgr *cm[2];
//    for (int i = 0; i < 2; ++i) {
//       cm[i] = new CirMgr;
//       cirMgr = cm[i];
//       if (!cirMgr->readCircuit(options[i])) {
//          curCmd = CIRINIT;
//          for (int j = 0; j <= i; ++j) delete cm[j];
//          cirMgr = 0;
//          return GV_CMD_EXEC_ERROR;
//       }
//    }

//    if (cm[0]->getNumPIs() != cm[1]->getNumPIs()) {
//       cout << "Error: numbers of PIs are different!!" << endl;
//       delete cm[0]; delete cm[1]; cirMgr = 0;
//       return GV_CMD_EXEC_ERROR;
//    }
//    if (cm[0]->getNumPOs() != cm[1]->getNumPOs()) {
//       cout << "Error: numbers of POs are different!!" << endl;
//       delete cm[0]; delete cm[1]; cirMgr = 0;
//       return GV_CMD_EXEC_ERROR;
//    }

//    cirMgr = new CirMgr;
//    if (!cirMgr->createMiter(cm[0], cm[1])) {
//       delete cirMgr;
//       cirMgr = 0;
//       return GV_CMD_EXEC_ERROR;
//    }
//    delete cm[0]; delete cm[1];

//    curCmd = CIRREAD;

//    return GV_CMD_EXEC_DONE;
// }

// void
// CirMiterCmd::usage(const bool& verbose) const
// {
//    cout << "Usage: CIRMiter <(string inFile1)> <(string inFile2)> " << endl;
// }

// void
// CirMiterCmd::help() const
// {
//    cout << setw(15) << left << "CIRMiter: "
//         << "create a miter circuit.\n";
// }

// //----------------------------------------------------------------------
// //    CIREFFort <(int effortLimit)>
// //----------------------------------------------------------------------
// GVCmdExecStatus
// CirEffortCmd::exec(const string& option)
// {
//    // check option
//    string token;
//    if (!GVCmdExec::lexSingleOption(option, token))
//       return GV_CMD_EXEC_ERROR;

//    int eff = -1;
//    if (token.empty())
//       return GVCmdExec::errorOption(GV_CMD_OPT_MISSING, "");
//    if (!myStr2Int(token, eff) || eff < 0)
//       return GVCmdExec::errorOption(GV_CMD_OPT_ILLEGAL, token);

//    effLimit = eff;
//    return GV_CMD_EXEC_DONE;
// }

// void
// CirEffortCmd::usage(const bool& verbose) const
// {
//    cout << "Usage: CIREFFort <(int effortLimit)>" << endl;
// }

// void
// CirEffortCmd::help() const
// {
//    cout << setw(15) << left << "CIREFFort: " << "set SAT proof effort\n";
// }
