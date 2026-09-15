package com.orderdelivery.orderservice.repository;

import com.orderdelivery.orderservice.entity.Location;
import org.springframework.data.jpa.repository.JpaRepository;

public interface LocationRepository extends JpaRepository<Location, Long> {
}
