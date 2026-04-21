/****************************************************************************
  FileName     [ proveBdd.cpp ]
  PackageName  [ prove ]
  Synopsis     [ For BDD-based verification ]
  Author       [ ]
  Copyright    [ Copyright(c) 2023-present DVLab, GIEE, NTU, Taiwan ]
****************************************************************************/

#include "bddMgrV.h"
#include "gvMsg.h"
// #include "gvNtk.h"
#include <iomanip>
#include <iostream>
#include <vector>

#include "cirGate.h"
#include "cirMgr.h"
#include "util.h"

void BddMgrV::buildPInitialState() {
    _isFixed = false;
    _reachStates.clear();

    // Initial state: all current-state FF variables are 0.
    BddNodeV init = BddNodeV::_one;
    for (unsigned i = 0, n = cirMgr->getNumLATCHs(); i < n; ++i) {
        BddNodeV cs = getBddNodeV(cirMgr->getRo(i)->getGid());
        if (cs() == 0) {
            gvMsg(GV_MSG_ERR) << "Missing BDD variable for RO gate "
                              << cirMgr->getRo(i)->getGid()
                              << " (run BSETOrder first)." << endl;
            _initState = size_t(0);
            return;
        }
        init &= ~cs;
    }
    _initState = init;
}

void BddMgrV::buildPTransRelation() {
    // TR  = /\_i (ns_i <-> F_i(cs, pi))
    // TRI = /\_i (cs_i <-> F_i(ns, pi))  (for potential backward usage)
    BddNodeV tr  = BddNodeV::_one;
    BddNodeV tri = BddNodeV::_one;

    for (unsigned i = 0, n = cirMgr->getNumLATCHs(); i < n; ++i) {
        gv::cir::CirRiGate* ri = cirMgr->getRi(i);
        gv::cir::CirRoGate* ro = cirMgr->getRo(i);

        BddNodeV nsVar = getBddNodeV(ri->getName());
        BddNodeV csVar = getBddNodeV(ro->getGid());
        BddNodeV f     = getBddNodeV(ri->getGid());
        if (nsVar() == 0 || csVar() == 0 || f() == 0) {
            gvMsg(GV_MSG_ERR) << "Missing BDD(s) for latch index " << i
                              << " (run BSETOrder and BCONStruct -All first)."
                              << endl;
            _tr  = size_t(0);
            _tri = size_t(0);
            return;
        }
        tr &= ~(nsVar ^ f);
        tri &= ~(csVar ^ f);
    }
    _tr  = tr;
    _tri = tri;
}

BddNodeV BddMgrV::restrict(const BddNodeV& f, const BddNodeV& g) {
    if (g == BddNodeV::_zero) {
        cout << "Error in restrict!!" << endl;
    }
    if (g == BddNodeV::_one) {
        return f;
    }
    if (f == BddNodeV::_zero || f == BddNodeV::_one) {
        return f;
    }
    unsigned a = g.getLevel();
    if (g.getLeftCofactor(a) == BddNodeV::_zero) {
        return restrict(f.getRightCofactor(a), g.getRightCofactor(a));
    }
    if (g.getRightCofactor(a) == BddNodeV::_zero) {
        return restrict(f.getLeftCofactor(a), g.getLeftCofactor(a));
    }
    if (f.getLeftCofactor(a) == f.getRightCofactor(a)) {
        return restrict(f, g.getLeftCofactor(a) | g.getRightCofactor(a));
    }
    BddNodeV newNode =
        (~getSupport(a)& restrict(f.getRightCofactor(a),
                                  g.getRightCofactor(a))) |
        (getSupport(a)& restrict(f.getLeftCofactor(a), g.getLeftCofactor(a)));
    return newNode;
}

void BddMgrV::buildPImage(int level) {
    if (_initState() == 0 || _tr() == 0) return;
    if (_reachStates.empty()) _reachStates.push_back(_initState);
    _isFixed = false;

    for (int i = 0; i < level; ++i) {
        BddNodeV cur  = _reachStates.back();
        BddNodeV next = ns_to_cs(find_ns(cur));
        BddNodeV uni  = cur | next;
        if (uni == cur) {
            _isFixed = true;
            cout << "Fixed point is reached (time : " << i << ")" << endl;
            break;
        }
        _reachStates.push_back(uni);
    }
}

void BddMgrV::runPCheckProperty(const string& name, BddNodeV monitor) {
    BddNodeV reached = getPReachState();
    BddNodeV bad     = reached & monitor;
    if (bad == BddNodeV::_zero) {
        cout << "Monitor \"" << name << "\" is safe." << endl;
    } else {
        cout << "Monitor \"" << name << "\" is violated." << endl;
    }
}

BddNodeV
BddMgrV::find_ns(BddNodeV cs) {
    // EXISTS_{PI,CS} [ cs(PI,CS) & TR(PI,CS,NS) ] = NS-space set
    BddNodeV img = cs & _tr;
    unsigned nPi = cirMgr->getNumPIs();
    unsigned nL  = cirMgr->getNumLATCHs();
    for (unsigned lv = 1; lv <= nPi + nL; ++lv)
        img = img.exist(lv);
    return img;
}

BddNodeV
BddMgrV::ns_to_cs(BddNodeV ns) {
    // Move NS variable block [nPi+nL+1, ...] down to CS block [nPi+1, ...]
    unsigned nPi = cirMgr->getNumPIs();
    unsigned nL  = cirMgr->getNumLATCHs();
    if (nL == 0) return ns;
    bool moved = false;
    BddNodeV csSpace = ns.nodeMove(nPi + nL + 1, nPi + 1, moved);
    if (!moved) return ns;
    return csSpace;
}
