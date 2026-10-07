// This consumer is built against installed headers and the installed shared library.
#include <sage-einsums/api/api.hpp>
#include <sage-einsums/tensor.hpp>
#include <cassert>
#include <thread>
#include <type_traits>
using namespace sage_cpp::api;
static_assert(std::is_same_v<decltype(std::declval<RuntimeTensorD&>().values()),std::span<double>>);
static_assert(std::is_same_v<decltype(std::declval<const RuntimeTensorD&>().values()),std::span<const double>>);
static_assert(std::is_same_v<decltype(std::declval<RuntimeTensorD&>().at(Shape{})),double&>);
static_assert(std::is_same_v<decltype(std::declval<const RuntimeTensorD&>().at(Shape{})),const double&>);
static_assert(std::is_copy_constructible_v<RuntimeTensorD> && std::is_move_constructible_v<RuntimeTensorD>);
static_assert(!std::is_copy_constructible_v<runtime::Section>);
static_assert(noexcept(sage_api_request(nullptr,0)) && noexcept(sage_api_free(nullptr)));
int main() {
 RuntimeTensorD source({2,2},{1,2,3,4});const auto& constant=source;
 auto owned=source;auto alias=source.view();const auto read=constant.view();
 alias.at({0,0})=9;assert(owned.at({0,0})==1 && read.at({0,0})==9);
 auto survivor=[](){RuntimeTensorD a({1},{7});return a.view();}();
 assert(survivor.at({0})==7);
 RuntimeTensorF f({1},{1.f});RuntimeTensorC c({1},{{1.f,2.f}});RuntimeTensorZ z({1},{{1.,2.}});
 assert(f.at({0})==1.f && c.at({0}).imag()==2.f && z.at({0}).imag()==2.);
 std::vector<std::thread> workers;
 for(unsigned i=0;i<8;++i)workers.emplace_back([i](){
  for(unsigned j=0;j<64;++j){
   auto key=std::to_string(i);runtime::set("int",key,std::int64_t(j));
   assert(std::get<std::int64_t>(runtime::get("int",key))==j);
   const char input[]="{\"op\":\"zeros\",\"params\":{\"shape\":[2,3]}}";
   auto* output=sage_api_request(input,sizeof(input)-1);assert(output);
   auto result=Json::parse(output);sage_api_free(output);
   assert(result.at("ok").at("arrays").at(0).at("shape")==Json::array({2,3}));
  }
 });
 for(auto& worker:workers)worker.join();
}
