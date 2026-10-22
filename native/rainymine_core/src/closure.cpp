#include "mineflow.h"
#include <cstdint>
using namespace mvd::mineflow;
extern "C" int rm_closure(int64_t n,const int64_t* values,int64_t m,const int64_t* edges,
                          int64_t nx,int64_t ny,int64_t nz,int64_t rx,int64_t ry,uint8_t* out) noexcept {
    try {
        std::shared_ptr<IPrecedenceConstraints> pre;
        if(nx>0) {
            PrecedencePattern pattern;
            for(int64_t x=-rx;x<=rx;++x) for(int64_t y=-ry;y<=ry;++y)
                pattern.Offsets.push_back(Vector3IT{x,y,1});
            pre=std::make_shared<Regular3DBlockModelPatternPrecedence>(nx,ny,nz,pattern);
        } else {
            auto explicit_pre=std::make_shared<ExplicitPrecedence>(n);
            for(int64_t i=0;i<m;++i)explicit_pre->AddPrecedenceConstraint(edges[2*i],edges[2*i+1]);
            pre=explicit_pre;
        }
        VecBlockValues weights(n);
        for(int64_t i=0;i<n;++i)weights.SetBlockValueSI(i,values[i]);
        PseudoSolver solver(pre,&weights);solver.Solve();
        for(int64_t i=0;i<n;++i)out[i]=solver.InMinimumCut(i)?1:0;
        return 0;
    } catch(...) { return 1; }
}
