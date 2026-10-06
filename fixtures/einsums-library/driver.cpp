// SAGE bounded Einsums v1.1.5 tensor harness. Einsums is MIT licensed;
// the unmodified upstream implementation and license are captured per run.
#include <Einsums/Tensor.hpp>
#include <Einsums/TensorAlgebra.hpp>
#include <Einsums/Profile/Timer.hpp>
#include <Einsums/LinearAlgebra.hpp>
#include <Einsums/FFT.hpp>
#include <Einsums/TensorUtilities/RMSD.hpp>
#include <cmath>
#include <cstdio>
#include <cstdint>

extern "C" int einsums_kernel(const unsigned char *bytes) {
    unsigned op = bytes[0], m = bytes[1], k = bytes[2], n = bytes[3];
    if (op > 22 || m < 1 || m > 4 || k < 1 || k > 4 || n < 1 || n > 4) return 65;
    einsums::profile::initialize();
    using einsums::Tensor;
    using einsums::Indices;
    using namespace einsums::tensor_algebra;
    using namespace einsums::index;
    Tensor<double, 2> A{"A", m, k};
    Tensor<double, 2> B{"B", op == 4 ? k : m, op == 4 ? n : k};
    for (size_t r = 0; r < A.dim(0); ++r)
        for (size_t c = 0; c < A.dim(1); ++c)
            A(r, c) = static_cast<int8_t>(bytes[4 + r * k + c]) / 8.0;
    for (size_t r = 0; r < B.dim(0); ++r)
        for (size_t c = 0; c < B.dim(1); ++c)
            B(r, c) = static_cast<int8_t>(bytes[20 + r * B.dim(1) + c]) / 8.0;
    unsigned rows = op == 3 ? k : m;
    unsigned cols = op == 3 ? m : (op == 4 ? n : k);
    if (op == 9 || op == 13) cols = 1;
    if (op == 10 || op == 15 || op == 16) rows = cols = 1;
    if (op == 17 || op == 19) cols = m;
    if (op == 18) { rows = 1; cols = m; }
    if (op == 20 || op == 21) { rows = k; cols = 2; }
    if (op == 22) { rows = 1; cols = k; }
    Tensor<double, 2> C{"C", rows, cols};
    C.zero();
    namespace la = einsums::linear_algebra;
    switch (op) {
    case 0: C = A; break;
    case 1: C = A + B; break;
    case 2: C = A * B; break;
    case 3: permute(Indices{i, j}, &C, Indices{j, i}, A); break;
    case 4: einsum(Indices{i, j}, &C, Indices{i, l}, A, Indices{l, j}, B); break;
    case 5: C = (static_cast<int8_t>(bytes[20]) / 8.0) * A; break;
    case 6: C = A - B; break;
    case 7:
        for (size_t r=0; r<m; ++r) for (size_t c=0; c<k; ++c) B(r,c)=std::abs(B(r,c))+1.;
        C = A / B; break;
    case 8: C = -A; break;
    case 9: C = Tensor<double,2>(A(einsums::All,einsums::Range{0,1})); break;
    case 10: C(0,0) = la::dot(A,B); break;
    case 11: C = B; la::axpy(2., A, &C); break;
    case 12: C = B; la::axpby(2., A, -0.5, &C); break;
    case 13: {
        Tensor<double,1> x{"x",k}, y{"y",m};
        for (size_t c=0;c<k;++c) x(c)=static_cast<int8_t>(bytes[20+c])/8.;
        y.zero();la::gemv<false>(1.,A,x,0.,&y);
        for (size_t r=0;r<m;++r) C(r,0)=y(r);break;
    }
    case 14: {
        Tensor<double,1> x{"x",m}, y{"y",k};
        for(size_t r=0;r<m;++r)x(r)=static_cast<int8_t>(bytes[4+r])/8.;
        for(size_t c=0;c<k;++c)y(c)=static_cast<int8_t>(bytes[20+c])/8.;
        C=A;la::ger(2.,x,y,&C);break;
    }
    case 15: C(0,0)=la::vec_norm(A);break;
    case 16: C(0,0)=einsums::rmsd(A,B);break;
    case 17: case 18: {
        Tensor<double,2> gram{"gram",m,m};gram.zero();
        einsum(Indices{i,j},&gram,Indices{i,l},A,Indices{j,l},A);
        for(size_t r=0;r<m;++r)gram(r,r)+=1.;
        if(op==17){la::invert(&gram);C=gram;}
        else{Tensor<double,1> eigen{"eigen",m};la::syev<false>(&gram,&eigen);
            for(size_t r=0;r<m;++r)C(0,r)=eigen(r);}
        break;
    }
    case 19: {
        // The pinned q() wrapper only supports the square shape safely.
        Tensor<double,2> square{"qr input",m,m};square.zero();
        einsum(Indices{i,j},&square,Indices{i,l},A,Indices{j,l},A);
        for(size_t r=0;r<m;++r)square(r,r)+=1.;
        auto [packed,tau]=la::qr(square); auto Q=la::q(packed,tau);
        const size_t inner=m;
        for(size_t r=0;r<m;++r)for(size_t c=0;c<m;++c)
            for(size_t t=0;t<inner;++t)if(t<=c)C(r,c)+=Q(r,t)*packed(t,c);
        break;
    }
    case 20: case 21: {
        Tensor<std::complex<double>,1> input{"input",k},output{"output",k};
        for(size_t t=0;t<k;++t)input(t)={static_cast<int8_t>(bytes[4+t])/8.,static_cast<int8_t>(bytes[20+t])/8.};
        if(op==20)einsums::fft::fft(input,&output);else einsums::fft::ifft(input,&output);
        for(size_t t=0;t<k;++t){C(t,0)=output(t).real();C(t,1)=output(t).imag();}
        break;
    }
    case 22: {
        auto frequencies=einsums::fft::fftfreq(k);
        for(size_t t=0;t<k;++t)C(0,t)=frequencies(t);break;
    }
    }
    // Shape, strides and indexed values are all observable; data are row-major.
    std::printf("{\"shape\":[[%zu,%zu]],\"strides\":[[%zu,%zu]],\"values\":[",
                C.dim(0), C.dim(1), C.stride(0), C.stride(1));
    for (size_t r = 0; r < C.dim(0); ++r) {
        std::printf("%s[", r ? "," : "");
        for (size_t c = 0; c < C.dim(1); ++c)
            std::printf("%s%.17g", c ? "," : "", C(r, c));
        std::printf("]");
    }
    std::printf("]}\n");
    return 0;
}

#ifndef SAGE_KERNEL_ONLY
int main(int argc, char **argv) {
    if (argc != 2) return 64;
    FILE *fp = std::fopen(argv[1], "rb");
    if (!fp) return 65;
    unsigned char bytes[37]{};
    size_t size = std::fread(bytes, 1, sizeof(bytes), fp);
    std::fclose(fp);
    if (size != 36) return 65;
    return einsums_kernel(bytes);
}
#endif
