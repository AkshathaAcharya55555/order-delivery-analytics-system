package com.orderdelivery.deliveryservice.repository;

import com.orderdelivery.deliveryservice.entity.Rider;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface RiderRepository extends JpaRepository<Rider, Long> {
    Page<Rider> findAll(Pageable pageable);

    List<Rider> findByCityAndActiveTrueAndAvailableTrue(String city);
}
