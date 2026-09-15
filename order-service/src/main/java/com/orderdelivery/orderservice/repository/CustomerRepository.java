package com.orderdelivery.orderservice.repository;

import com.orderdelivery.orderservice.entity.Customer;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CustomerRepository extends JpaRepository<Customer, Long> {
}
