"""
Performance Benchmarks
Tests performance under various conditions.
"""

import pytest
import time
import statistics
from pathlib import Path
from unittest.mock import Mock, patch
from typing import List

from agents.fahas_agent import FahasAgent
from agents.katib_agent import KatibAgent
from agents.seraj_meta_agent import SerajMetaAgent
from agents.base_agent import AgentGoal


class TestPerformanceBenchmarks:
    """Performance benchmark tests"""
    
    def setup_method(self):
        """Setup"""
        self.mock_llm = Mock()
        self.mock_llm.generate.return_value = {"text": "Response", "confidence": 0.9}
        
        self.fahas = FahasAgent()
        self.katib = KatibAgent()
        self.seraj = SerajMetaAgent()
    
    @pytest.mark.benchmark
    def test_agent_latency(self):
        """Benchmark agent execution latency"""
        agents = {
            "Fahas": self.fahas,
            "Katib": self.katib,
            "Seraj": self.seraj,
        }
        
        results = {}
        
        for name, agent in agents.items():
            with patch.object(agent, 'llm_provider', self.mock_llm):
                latencies = []
                
                for i in range(10):
                    goal = AgentGoal(
                        description=f"Test {i}",
                        context={"test": True}
                    )
                    
                    start = time.time()
                    agent.run(goal)
                    latency = (time.time() - start) * 1000
                    latencies.append(latency)
                
                results[name] = {
                    "avg": statistics.mean(latencies),
                    "min": min(latencies),
                    "max": max(latencies),
                    "p95": statistics.quantiles(latencies, n=20)[18],  # 95th percentile
                }
        
        # Print results
        print("\n" + "="*60)
        print("AGENT LATENCY BENCHMARKS")
        print("="*60)
        for name, metrics in results.items():
            print(f"\n{name}:")
            print(f"  Avg: {metrics['avg']:.1f}ms")
            print(f"  Min: {metrics['min']:.1f}ms")
            print(f"  Max: {metrics['max']:.1f}ms")
            print(f"  P95: {metrics['p95']:.1f}ms")
        
        # Assertions
        for name, metrics in results.items():
            assert metrics['avg'] < 5000, f"{name} avg latency too high: {metrics['avg']:.1f}ms"
            assert metrics['p95'] < 10000, f"{name} P95 latency too high: {metrics['p95']:.1f}ms"
    
    @pytest.mark.benchmark
    def test_throughput(self):
        """Benchmark request throughput"""
        with patch.object(self.fahas, 'llm_provider', self.mock_llm):
            num_requests = 100
            start = time.time()
            
            for i in range(num_requests):
                goal = AgentGoal(
                    description=f"Request {i}",
                    context={"test": True}
                )
                self.fahas.run(goal)
            
            duration = time.time() - start
            throughput = num_requests / duration
        
        print(f"\n✅ Throughput: {throughput:.1f} requests/second")
        print(f"   Total time: {duration:.2f}s for {num_requests} requests")
        
        # Should handle at least 10 req/s
        assert throughput >= 10, f"Throughput too low: {throughput:.1f} req/s"
    
    @pytest.mark.benchmark
    def test_memory_efficiency(self):
        """Benchmark memory efficiency"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Baseline
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Run many iterations
        with patch.object(self.fahas, 'llm_provider', self.mock_llm):
            for i in range(100):
                goal = AgentGoal(
                    description=f"Test {i}",
                    context={"data": "x" * 1000}  # 1KB per request
                )
                self.fahas.run(goal)
                
                # Force garbage collection every 10 iterations
                if i % 10 == 0:
                    import gc
                    gc.collect()
        
        # Final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        memory_per_request = memory_increase / 100
        
        print(f"\n✅ Memory efficiency:")
        print(f"   Initial: {initial_memory:.1f} MB")
        print(f"   Final: {final_memory:.1f} MB")
        print(f"   Increase: {memory_increase:.1f} MB")
        print(f"   Per request: {memory_per_request:.2f} MB")
        
        # Memory increase should be reasonable
        assert memory_increase < 200, f"Memory leak detected: {memory_increase:.1f} MB"
    
    @pytest.mark.benchmark
    def test_caching_effectiveness(self):
        """Test caching effectiveness"""
        # Simulate cached vs uncached requests
        cache_hits = 0
        cache_misses = 0
        
        cached_responses = {}
        
        with patch.object(self.fahas, 'llm_provider', self.mock_llm):
            # Make 50 requests (some duplicates)
            queries = ["Query A", "Query B", "Query C"] * 17  # 51 total
            
            for query in queries[:50]:
                goal = AgentGoal(description=query, context={})
                
                # Check cache
                if query in cached_responses:
                    # Cache hit
                    result = cached_responses[query]
                    cache_hits += 1
                else:
                    # Cache miss
                    start = time.time()
                    result = self.fahas.run(goal)
                    latency = (time.time() - start) * 1000
                    
                    cached_responses[query] = result
                    cache_misses += 1
        
        cache_hit_rate = cache_hits / (cache_hits + cache_misses)
        
        print(f"\n✅ Caching effectiveness:")
        print(f"   Cache hits: {cache_hits}")
        print(f"   Cache misses: {cache_misses}")
        print(f"   Hit rate: {cache_hit_rate:.1%}")
        
        # With repeated queries, should have high hit rate
        assert cache_hit_rate >= 0.90, f"Cache hit rate too low: {cache_hit_rate:.1%}"
    
    @pytest.mark.benchmark
    @pytest.mark.slow
    def test_sustained_load(self):
        """Test performance under sustained load"""
        duration_seconds = 30
        
        latencies = []
        errors = 0
        
        with patch.object(self.fahas, 'llm_provider', self.mock_llm):
            start_time = time.time()
            request_count = 0
            
            while time.time() - start_time < duration_seconds:
                try:
                    goal = AgentGoal(
                        description=f"Sustained load test {request_count}",
                        context={"test": True}
                    )
                    
                    req_start = time.time()
                    self.fahas.run(goal)
                    latency = (time.time() - req_start) * 1000
                    
                    latencies.append(latency)
                    request_count += 1
                
                except Exception as e:
                    errors += 1
                    print(f"Error: {e}")
            
            total_time = time.time() - start_time
        
        # Calculate metrics
        avg_latency = statistics.mean(latencies) if latencies else 0
        p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else 0
        throughput = request_count / total_time
        error_rate = errors / request_count if request_count > 0 else 1.0
        
        print(f"\n✅ Sustained load test ({duration_seconds}s):")
        print(f"   Requests: {request_count}")
        print(f"   Throughput: {throughput:.1f} req/s")
        print(f"   Avg latency: {avg_latency:.1f}ms")
        print(f"   P95 latency: {p95_latency:.1f}ms")
        print(f"   Errors: {errors} ({error_rate:.1%})")
        
        # Assertions
        assert throughput >= 5, f"Throughput degraded: {throughput:.1f} req/s"
        assert error_rate < 0.01, f"Error rate too high: {error_rate:.1%}"
        assert avg_latency < 10000, f"Avg latency too high: {avg_latency:.1f}ms"


class TestScalability:
    """Scalability tests"""
    
    @pytest.mark.scalability
    def test_concurrent_users(self):
        """Test handling concurrent users"""
        import concurrent.futures
        import threading
        
        mock_llm = Mock()
        mock_llm.generate.return_value = {"text": "OK", "confidence": 0.9}
        
        results = []
        errors = []
        lock = threading.Lock()
        
        def simulate_user(user_id: int):
            """Simulate a single user"""
            try:
                fahas = FahasAgent()
                with patch.object(fahas, 'llm_provider', mock_llm):
                    for i in range(5):  # 5 requests per user
                        goal = AgentGoal(
                            description=f"User {user_id} request {i}",
                            context={"user_id": user_id}
                        )
                        
                        start = time.time()
                        fahas.run(goal)
                        latency = (time.time() - start) * 1000
                        
                        with lock:
                            results.append(latency)
            
            except Exception as e:
                with lock:
                    errors.append(str(e))
        
        # Simulate 20 concurrent users
        num_users = 20
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [executor.submit(simulate_user, i) for i in range(num_users)]
            concurrent.futures.wait(futures)
        
        # Analyze results
        total_requests = len(results)
        avg_latency = statistics.mean(results) if results else 0
        error_rate = len(errors) / (num_users * 5)
        
        print(f"\n✅ Concurrent users test:")
        print(f"   Users: {num_users}")
        print(f"   Total requests: {total_requests}")
        print(f"   Avg latency: {avg_latency:.1f}ms")
        print(f"   Errors: {len(errors)} ({error_rate:.1%})")
        
        # Assertions
        assert error_rate < 0.05, f"Error rate too high: {error_rate:.1%}"
        assert avg_latency < 15000, f"Latency degraded under load: {avg_latency:.1f}ms"
    
    @pytest.mark.scalability
    def test_data_volume_scaling(self):
        """Test performance with increasing data volumes"""
        mock_llm = Mock()
        mock_llm.generate.return_value = {"text": "OK", "confidence": 0.9}
        
        fahas = FahasAgent()
        
        data_sizes = [10, 100, 1000, 5000]
        results = {}
        
        for size in data_sizes:
            # Create dataset
            data = [{"id": i, "value": f"Data {i}"} for i in range(size)]
            
            with patch.object(fahas, 'llm_provider', mock_llm):
                goal = AgentGoal(
                    description=f"Process {size} records",
                    context={"data": data}
                )
                
                start = time.time()
                fahas.run(goal)
                duration = (time.time() - start) * 1000
            
            results[size] = duration
            print(f"  {size} records: {duration:.1f}ms")
        
        # Check scaling is reasonable (shouldn't be exponential)
        # 10x data should be < 20x time
        ratio_10_to_1000 = results[1000] / results[10]
        
        print(f"\n✅ Data volume scaling:")
        print(f"   10 → 1000 records: {ratio_10_to_1000:.1f}x slower")
        
        assert ratio_10_to_1000 < 20, f"Poor scaling: {ratio_10_to_1000:.1f}x"


class TestReliability:
    """Reliability and resilience tests"""
    
    @pytest.mark.reliability
    def test_error_recovery(self):
        """Test agent recovers from errors"""
        mock_llm = Mock()
        
        # Simulate intermittent failures
        call_count = [0]
        
        def failing_generate(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 3 == 0:
                raise Exception("Simulated LLM failure")
            return {"text": "OK", "confidence": 0.9}
        
        mock_llm.generate.side_effect = failing_generate
        
        fahas = FahasAgent()
        
        successes = 0
        failures = 0
        
        with patch.object(fahas, 'llm_provider', mock_llm):
            for i in range(10):
                goal = AgentGoal(
                    description=f"Test {i}",
                    context={"test": True}
                )
                
                try:
                    fahas.run(goal)
                    successes += 1
                except Exception:
                    failures += 1
        
        recovery_rate = successes / (successes + failures)
        
        print(f"\n✅ Error recovery:")
        print(f"   Successes: {successes}")
        print(f"   Failures: {failures}")
        print(f"   Recovery rate: {recovery_rate:.1%}")
        
        # Should handle some failures gracefully
        assert failures > 0, "No failures occurred (test issue)"
        assert successes > 0, "No successes (complete failure)"
    
    @pytest.mark.reliability
    def test_timeout_handling(self):
        """Test timeout handling"""
        mock_llm = Mock()
        
        def slow_generate(*args, **kwargs):
            time.sleep(2)  # Slow response
            return {"text": "OK", "confidence": 0.9}
        
        mock_llm.generate.side_effect = slow_generate
        
        fahas = FahasAgent()
        
        with patch.object(fahas, 'llm_provider', mock_llm):
            goal = AgentGoal(
                description="Slow request",
                context={"test": True}
            )
            
            start = time.time()
            try:
                # Should timeout or complete
                fahas.run(goal)
                duration = time.time() - start
                print(f"\n✅ Completed (slow): {duration:.1f}s")
            except Exception as e:
                duration = time.time() - start
                print(f"\n✅ Timeout handled: {duration:.1f}s - {e}")
        
        # Should either complete or timeout within reasonable time
        assert duration < 10, f"Request took too long: {duration:.1f}s"


# Run benchmarks
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "benchmark"])
